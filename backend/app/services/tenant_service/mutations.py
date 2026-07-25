"""Tenant mutation operations: create, update, delete."""

import logging
import secrets
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import (
    get_rls_context,
    restore_rls_context,
    set_internal_tenant_rls_context,
    set_rls_context,
)
from app.core.input_validation import (
    validate_client_prefix,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_username,
)
from app.core.encryption import encrypt_value
from app.core.redis_client import get_redis_manager
from app.core.security import get_password_hash
from app.repositories import (
    clients_repository,
    sessions_repository,
    tenants_repository,
    users_repository,
)
from app.models import Tenant, TenantSettings, User
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services.client_service import ClientService
from app.services.evolution_client import evolution_client
from .helpers import generate_unique_client_prefix
from .queries import get_tenant

logger = logging.getLogger(__name__)


async def create_tenant(
    db: AsyncSession, payload: TenantCreate
) -> tuple[Tenant, str | None]:
    username = validate_username(payload.username)
    full_name = validate_full_name(payload.full_name)
    email = validate_email(payload.email)
    phone = validate_phone(payload.phone)
    client_prefix = payload.client_prefix or await generate_unique_client_prefix(db)

    if payload.client_prefix and await tenants_repository.client_prefix_exists(
        db, client_prefix
    ):
        raise ValueError("Prefijo de cliente ya registrado")

    existing_username = await users_repository.get_by_username(db, username)
    if existing_username:
        raise ValueError("Username already registered")

    if phone:
        existing = await users_repository.get_by_phone(db, phone)
        if existing:
            raise ValueError("Phone already registered")

    plain_password = payload.password
    auto_generated = plain_password is None
    if plain_password is None:
        plain_password = secrets.token_urlsafe(16)

    user = User(
        username=username,
        password_hash=get_password_hash(plain_password),
        role="tenant",
    )
    db.add(user)
    await db.flush()

    profile = Tenant(
        owner_user_id=user.id,
        client_prefix=client_prefix,
        plan=payload.plan,
        name=full_name,
        email=email,
        whatsapp_phone=phone,
        evolution_instance_name=payload.evolution_instance_name,
        is_active=True,
    )
    db.add(profile)
    await db.flush()

    db.add(TenantSettings(tenant_id=profile.id, locale="en", timezone="UTC"))
    await db.flush()

    try:
        instance_data = await evolution_client.create_instance(
            payload.evolution_instance_name
        )
        if instance_data and instance_data.get("instance_id"):
            await evolution_client.register_webhook(instance_data["instance_id"])
            if instance_data.get("instance_token"):
                profile.evolution_instance_token = encrypt_value(
                    instance_data["instance_token"]
                )
    except Exception as exc:
        await db.rollback()
        raise ValueError(f"Failed to create Evolution instance: {exc}") from exc

    await db.commit()
    await restore_rls_context(db)

    created_profile = await get_tenant(db, profile.id)
    if created_profile is None:
        raise ValueError("Tenant could not be created")
    return created_profile, plain_password if auto_generated else None


async def _run_pro_to_starter_downgrade_effects(
    db: AsyncSession, profile: Tenant
) -> None:
    """Side effects when a tenant downgrades from pro to starter."""
    await sessions_repository.revoke_all_for_tenant_clients(db, profile.id)
    await db.commit()

    phone = validate_phone(profile.whatsapp_phone) if profile.whatsapp_phone else None
    manager = get_redis_manager()
    if manager is not None and phone:

        async def _delete_admin_session(client):
            await client.delete(f"session:admin:{phone}")

        try:
            await manager.execute(
                "clear_admin_session_on_downgrade", _delete_admin_session
            )
        except Exception:
            logger.warning(
                "Failed to clear admin WhatsApp session during downgrade tenant=%s",
                profile.id,
                exc_info=True,
            )

    if profile.evolution_instance_name and phone:
        try:
            await evolution_client.close_chat_session(
                instance=profile.evolution_instance_name,
                remote_jid=f"{phone}@s.whatsapp.net",
            )
        except Exception:
            logger.warning(
                "Failed to close Evolution session during downgrade tenant=%s",
                profile.id,
                exc_info=True,
            )


async def update_tenant(
    db: AsyncSession, tenant_id: UUID, payload: TenantUpdate
) -> Tenant | None:
    profile = await get_tenant(db, tenant_id)
    if profile is None:
        return None
    if profile.is_demo:
        raise ValueError("Demo Tenant must be managed through the Demo Tenant API")

    update_data = payload.model_dump(exclude_unset=True)

    if "full_name" in update_data and update_data["full_name"] is not None:
        update_data["full_name"] = validate_full_name(update_data["full_name"])
    if "email" in update_data:
        update_data["email"] = validate_email(update_data["email"])
    if "phone" in update_data:
        if update_data["phone"] is not None:
            update_data["phone"] = validate_phone(update_data["phone"])

    if "client_prefix" in update_data and update_data["client_prefix"] is not None:
        update_data["client_prefix"] = validate_client_prefix(
            update_data["client_prefix"]
        )

    if "phone" in update_data and update_data["phone"] != profile.phone:
        if update_data["phone"] is not None:
            existing = await users_repository.get_by_phone(db, update_data["phone"])
            if existing and existing[0].id != profile.owner_user_id:
                raise ValueError("Phone already registered")

    if (
        "client_prefix" in update_data
        and update_data["client_prefix"] != profile.client_prefix
    ):
        if await tenants_repository.client_prefix_exists(
            db, update_data["client_prefix"], profile.id
        ):
            raise ValueError("Prefijo de cliente ya registrado")
        client_service = ClientService()
        await client_service.sync_client_usernames_for_tenant(
            db, profile.id, update_data["client_prefix"]
        )

    old_plan = profile.plan
    new_plan = update_data.get("plan", old_plan)

    for field, value in update_data.items():
        setattr(profile, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("No se pudo actualizar el prefijo de cliente") from exc
    await restore_rls_context(db)

    if old_plan == "pro" and new_plan == "starter":
        await _run_pro_to_starter_downgrade_effects(db, profile)

    return await get_tenant(db, tenant_id)


async def delete_tenant(db: AsyncSession, tenant_id: UUID) -> bool:
    profile = await get_tenant(db, tenant_id)
    if profile is None:
        return False
    if profile.is_demo:
        raise ValueError("Demo Tenant must be managed through the Demo Tenant API")
    if profile.is_active:
        raise ValueError("Cannot delete active tenant. Deactivate first.")

    instance_name = profile.evolution_instance_name
    user = await users_repository.get(db, profile.owner_user_id)
    if user is None:
        return False

    previous_context = get_rls_context(db)
    await set_internal_tenant_rls_context(db, str(profile.id))
    try:
        clients = await clients_repository.get_clients_with_user(db, profile.id)
        client_users = [c.user for c in clients if c.user is not None]
        for client_user in client_users:
            await db.delete(client_user)
        await db.delete(user)
        await db.flush()
    finally:
        if previous_context is not None:
            await set_rls_context(
                db,
                previous_context["user_id"],
                previous_context["role"],
                previous_context["active_tenant_id"],
            )

    try:
        if instance_name:
            await evolution_client.delete_instance(instance_name)
    except Exception as exc:
        await db.rollback()
        raise ValueError(f"Failed to delete Evolution instance: {exc}") from exc

    await db.commit()
    await restore_rls_context(db)
    return True
