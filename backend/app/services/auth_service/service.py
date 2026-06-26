import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import set_internal_rls_context
from app.core.phone import normalize_phone
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    verify_password,
)
from app.models import RefreshSession, User
from app.repositories import (
    clients_repository,
    sessions_repository,
    tenants_repository,
    users_repository,
)


def _hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _verify_refresh_token(refresh_token: str, refresh_token_hash: str) -> bool:
    return hmac.compare_digest(_hash_refresh_token(refresh_token), refresh_token_hash)


class AuthService:
    async def authenticate(
        self, db: AsyncSession, username: str, password: str
    ) -> User | None:
        user = await users_repository.get_by_username(db, username)
        if not user:
            return None
        if user.role in {"tenant", "client"}:
            active_tenant_id = await self._active_tenant_id_for_user(db, user)
            if active_tenant_id is None:
                return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def _active_tenant_id_for_user(
        self, db: AsyncSession, user: User
    ) -> UUID | None:
        if user.role == "tenant":
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active_by_owner(db, user.id)
            return tenant.id if tenant else None
        if user.role != "client":
            return None
        await set_internal_rls_context(db)
        row = await clients_repository.get_active_client_tenant_join(db, user.id)
        if not row:
            return None
        tenant = row[0].tenant
        if tenant.plan != "pro":
            return None
        return row[0].tenant_id

    async def _tenant_plan_for_user(
        self, db: AsyncSession, user: User, active_tenant_id: UUID | None
    ) -> str | None:
        if user.role == "tenant":
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active_by_owner(db, user.id)
            return tenant.plan if tenant else None
        if user.role == "master" and active_tenant_id is not None:
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active(db, active_tenant_id)
            return tenant.plan if tenant else None
        if user.role == "client" and active_tenant_id is not None:
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active(db, active_tenant_id)
            return tenant.plan if tenant else None
        return None

    async def create_tokens(
        self, db: AsyncSession, user: User, active_tenant_id: UUID | None = None
    ) -> dict | None:
        if user.role in {"tenant", "client"}:
            active_tenant_id = await self._active_tenant_id_for_user(db, user)
            if active_tenant_id is None:
                return None
        tenant_plan = await self._tenant_plan_for_user(db, user, active_tenant_id)
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role,
            active_tenant_id=str(active_tenant_id) if active_tenant_id else None,
        )
        refresh_token = create_refresh_token(subject=str(user.id))
        generate_secure_token()
        refresh_token_hash = _hash_refresh_token(refresh_token)

        session = RefreshSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
            revoked=False,
        )
        db.add(session)
        await db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {"id": user.id, "role": user.role, "username": user.username},
            "active_tenant_id": active_tenant_id,
            "tenant_plan": tenant_plan,
        }

    async def refresh_access_token(
        self, db: AsyncSession, refresh_token: str, active_tenant_id: UUID | None = None
    ) -> dict | None:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                return None
            user_id = UUID(payload.get("sub"))
        except (ValueError, TypeError):
            return None

        sessions = await sessions_repository.get_valid_sessions(db, user_id)

        valid_session = None
        for session in sessions:
            if _verify_refresh_token(refresh_token, session.refresh_token_hash):
                valid_session = session
                break

        if not valid_session:
            return None

        valid_session.revoked = True
        user = await users_repository.get(db, user_id)
        if not user:
            await db.commit()
            return None

        if user.role in {"tenant", "client"}:
            active_tenant_id = await self._active_tenant_id_for_user(db, user)
            if active_tenant_id is None:
                await db.commit()
                return None

        if user.role == "master" and active_tenant_id:
            await set_internal_rls_context(db)
            tenant = await tenants_repository.get_active(db, active_tenant_id)
            if tenant is None:
                active_tenant_id = None
        return await self.create_tokens(db, user, active_tenant_id)

    async def switch_tenant(
        self, db: AsyncSession, user: User, tenant_id: UUID | None
    ) -> dict | None:
        if user.role != "master":
            return None
        if tenant_id is not None:
            tenant = await tenants_repository.get_active(db, tenant_id)
            if tenant is None:
                return None
        return await self.create_tokens(db, user, tenant_id)

    async def revoke_refresh_token(self, db: AsyncSession, refresh_token: str) -> bool:
        """Revoke a refresh token (logout)."""
        sessions = await sessions_repository.get_all_unrevoked(db)
        for session in sessions:
            if _verify_refresh_token(refresh_token, session.refresh_token_hash):
                session.revoked = True
                await db.commit()
                return True
        return False

    async def identify_by_phone(self, db: AsyncSession, phone: str) -> dict | None:
        canonical = normalize_phone(phone)
        if canonical is None:
            return None
        await set_internal_rls_context(db)
        result = await users_repository.get_by_phone(db, canonical)
        if not result:
            return None
        user, _ = result
        if user.role == "tenant":
            profile = await tenants_repository.get_by_owner(db, user.id)
            if profile and not profile.is_active:
                return None
        return {"user_id": user.id, "role": user.role, "username": user.username}

    async def identify_by_lid(self, db: AsyncSession, lid: str) -> dict | None:
        """Resolve identity by WhatsApp LID.

        Checks master_profiles, tenants, and clients for a match.
        Returns the same shape as ``identify_by_phone``.
        """
        if not lid or not lid.strip():
            return None
        await set_internal_rls_context(db)

        # Check master/tenant profiles via user table
        result = await users_repository.get_by_lid(db, lid)
        if result:
            user, role = result
            if role == "tenant":
                profile = await tenants_repository.get_by_owner(db, user.id)
                if profile and not profile.is_active:
                    return None
            return {"user_id": user.id, "role": role, "username": user.username}

        # Check client profiles
        client = await clients_repository.get_client_by_lid(db, lid)
        if client and client.tenant and client.tenant.is_active:
            user = await users_repository.get(db, client.owner_user_id)
            if user:
                return {
                    "user_id": user.id,
                    "role": "client",
                    "username": user.username,
                }

        return None
