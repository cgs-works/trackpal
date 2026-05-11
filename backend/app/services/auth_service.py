from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    verify_password,
)
from app.crud import users as user_crud
from app.models import RefreshSession, TenantProfile, User


def _hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _verify_refresh_token(refresh_token: str, refresh_token_hash: str) -> bool:
    return hmac.compare_digest(_hash_refresh_token(refresh_token), refresh_token_hash)


class AuthService:
    async def authenticate(
        self, db: AsyncSession, username: str, password: str
    ) -> User | None:
        user = await user_crud.get_by_username(db, username)
        if not user:
            return None
        if user.role == "tenant":
            result = await db.execute(
                select(TenantProfile).where(TenantProfile.id == user.id)
            )
            profile = result.scalar_one_or_none()
            if profile and not profile.is_active:
                return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def create_tokens(self, db: AsyncSession, user: User) -> dict:
        access_token = create_access_token(subject=str(user.id), role=user.role)
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
        }

    async def refresh_access_token(
        self, db: AsyncSession, refresh_token: str
    ) -> dict | None:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                return None
            user_id = UUID(payload.get("sub"))
        except (ValueError, TypeError):
            return None

        result = await db.execute(
            select(RefreshSession).where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked == False,  # noqa: E712
                RefreshSession.expires_at > datetime.now(timezone.utc),
            )
        )
        sessions = result.scalars().all()

        valid_session = None
        for session in sessions:
            if _verify_refresh_token(refresh_token, session.refresh_token_hash):
                valid_session = session
                break

        if not valid_session:
            return None

        valid_session.revoked = True
        user = await user_crud.get(db, user_id)
        if not user:
            await db.commit()
            return None

        return await self.create_tokens(db, user)

    async def revoke_refresh_token(self, db: AsyncSession, refresh_token: str) -> bool:
        """Revoke a refresh token (logout)."""
        result = await db.execute(
            select(RefreshSession).where(RefreshSession.revoked == False)  # noqa: E712
        )
        sessions = result.scalars().all()
        for session in sessions:
            if _verify_refresh_token(refresh_token, session.refresh_token_hash):
                session.revoked = True
                await db.commit()
                return True
        return False

    async def identify_by_phone(self, db: AsyncSession, phone: str) -> dict | None:
        result = await user_crud.get_by_phone(db, phone)
        if not result:
            return None
        user, _ = result
        if user.role == "tenant":
            profile_result = await db.execute(
                select(TenantProfile).where(TenantProfile.id == user.id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile and not profile.is_active:
                return None
        return {"user_id": user.id, "role": user.role, "username": user.username}
