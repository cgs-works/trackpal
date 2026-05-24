from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_rls_context, restore_rls_context, set_internal_tenant_rls_context, set_rls_context
from app.core.errors import UserFacingError
from app.core.input_validation import (
    validate_client_local_username,
    validate_full_name,
    validate_phone,
    validate_password_policy,
)
from app.core.security import get_password_hash
from app.repositories import clients_repository, sessions_repository, tenants_repository, users_repository
from app.models import Client, Tenant, User
from app.schemas.client import ClientCreate, ClientUpdate


def build_client_username(client_prefix: str, local_username: str) -> str:
    return f"{client_prefix}_{local_username}"


class ClientService:
    async def _get_tenant(self, db: AsyncSession, tenant_id: UUID) -> Tenant | None:
        return await tenants_repository.get(db, tenant_id)

    async def _get_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> Client | None:
        return await clients_repository.get(db, tenant_id, client_id)

    async def list_clients(self, db: AsyncSession, tenant_id: UUID) -> list[Client]:
        return await clients_repository.list_clients(db, tenant_id)

    async def get_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> Client | None:
        return await self._get_client(db, tenant_id, client_id)

    async def create_client(
        self, db: AsyncSession, tenant_id: UUID, payload: ClientCreate
    ) -> Client | None:
        tenant = await self._get_tenant(db, tenant_id)
        if tenant is None:
            return None

        full_name = validate_full_name(payload.full_name)
        local_username = validate_client_local_username(payload.local_username)
        phone = validate_phone(payload.phone)
        password = validate_password_policy(payload.password)
        technical_username = build_client_username(tenant.client_prefix, local_username)

        if await clients_repository.local_username_exists(db, tenant_id, local_username):
            raise UserFacingError("client_local_username_exists")
        if phone and await clients_repository.phone_exists(db, tenant_id, phone):
            raise UserFacingError("phone_already_registered")
        if await users_repository.username_exists(db, technical_username):
            raise UserFacingError("username_already_registered")

        user = User(
            username=technical_username,
            password_hash=get_password_hash(password),
            role="client",
        )
        db.add(user)
        await db.flush()

        client = Client(
            tenant_id=tenant.id,
            owner_user_id=user.id,
            full_name=full_name,
            local_username=local_username,
            phone=phone,
            is_active=True,
        )
        db.add(client)

        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise UserFacingError("client_create_failed") from exc

        await restore_rls_context(db)
        return await self._get_client(db, tenant_id, client.id)

    async def update_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID, payload: ClientUpdate
    ) -> Client | None:
        client = await self._get_client(db, tenant_id, client_id)
        if client is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)

        if "full_name" in update_data and update_data["full_name"] is not None:
            update_data["full_name"] = validate_full_name(update_data["full_name"])
        if "local_username" in update_data and update_data["local_username"] is not None:
            update_data["local_username"] = validate_client_local_username(
                update_data["local_username"]
            )
        if "phone" in update_data:
            update_data["phone"] = validate_phone(update_data["phone"])

        new_local_username = update_data.get("local_username", client.local_username)
        technical_username = build_client_username(
            client.tenant.client_prefix, new_local_username
        )

        if new_local_username != client.local_username:
            if await clients_repository.local_username_exists(
                db, tenant_id, new_local_username, client.id
            ):
                raise UserFacingError("client_local_username_exists")

        if "phone" in update_data and update_data["phone"] != client.phone:
            if update_data["phone"] is not None and await clients_repository.phone_exists(
                db, tenant_id, update_data["phone"], client.id
            ):
                raise UserFacingError("phone_already_registered")

        if technical_username != client.user.username and await users_repository.username_exists(
            db, technical_username, client.user.id
        ):
            raise UserFacingError("username_already_registered")

        for field, value in update_data.items():
            setattr(client, field, value)
        client.user.username = technical_username

        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise UserFacingError("client_update_failed") from exc

        await restore_rls_context(db)
        return await self._get_client(db, tenant_id, client_id)

    async def deactivate_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> Client | None:
        client = await self._get_client(db, tenant_id, client_id)
        if client is None:
            return None
        client.is_active = False
        await sessions_repository.revoke_all_for_user(db, client.owner_user_id)
        await db.commit()
        await restore_rls_context(db)
        return await self._get_client(db, tenant_id, client_id)

    async def activate_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> Client | None:
        client = await self._get_client(db, tenant_id, client_id)
        if client is None:
            return None
        client.is_active = True
        await db.commit()
        await restore_rls_context(db)
        return await self._get_client(db, tenant_id, client_id)

    async def delete_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> bool:
        client = await self._get_client(db, tenant_id, client_id)
        if client is None:
            return False
        if client.is_active:
            raise UserFacingError("client_delete_active")

        user = client.user or await users_repository.get(db, client.owner_user_id)
        if user is None:
            return False

        await db.delete(user)
        await db.commit()
        await restore_rls_context(db)
        return True

    async def sync_client_usernames_for_tenant(
        self, db: AsyncSession, tenant_id: UUID, new_prefix: str
    ) -> None:
        previous_context = get_rls_context(db)
        await set_internal_tenant_rls_context(db, str(tenant_id))
        try:
            clients = await clients_repository.get_clients_with_user(db, tenant_id)
            for client in clients:
                client.user.username = build_client_username(new_prefix, client.local_username)
        finally:
            if previous_context is not None:
                await set_rls_context(
                    db,
                    previous_context["user_id"],
                    previous_context["role"],
                    previous_context["active_tenant_id"],
                )
