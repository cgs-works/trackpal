"""Tenant self-deletion orchestration — export cancel, R2 purge, Evolution delete,
database cascade, and session teardown.

Operates in external-first order so that a rare final DB failure leaves the
Tenant in a retryable state with external objects already absent.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_rls_context, restore_rls_context, set_rls_context
from app.core.security import verify_password
from app.models import Client as ClientModel
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories import export_jobs_repository, sessions_repository
from app.services import export_service
from app.services.evolution_client import evolution_client
from app.services.export_storage import (
    StorageObjectNotFoundError,
    StorageOperationError,
)
from app.services.step_up_limiter import StepUpError, StepUpRateLimiter

logger = logging.getLogger(__name__)

CANCEL_WAIT_SECONDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _validate_destructive_word(word: str, locale: str) -> bool:
    """Validate the destructive confirmation word.

    Accepts ``DELETE`` for english and ``ELIMINAR`` for spanish locales.
    Comparison is case-insensitive after trimming.
    """
    normalized = word.strip().upper()
    if locale == "es":
        return normalized == "ELIMINAR"
    return normalized == "DELETE"


async def _cancel_export_and_wait(
    db: AsyncSession,
    tenant_id: UUID,
    actor_id: UUID,
) -> tuple[bool, str | None]:
    """Cancel an in-progress export and wait up to CANCEL_WAIT_SECONDS.

    Returns ``(True, None)`` if cancellation completed (or no job to cancel).
    Returns ``(False, error_message)`` if the timeout was reached.
    """
    job = await export_service.cancel_export(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
    )
    if job is None:
        return True, None

    deadline = _now().timestamp() + CANCEL_WAIT_SECONDS
    while _now().timestamp() < deadline:
        await asyncio.sleep(1)
        refreshed = await export_jobs_repository.get_by_id(db, job.id)
        if refreshed is None or refreshed.status not in ("pending", "processing"):
            return True, None

    return False, "Export cancellation timed out. Try again."


async def _purge_export_storage(
    db: AsyncSession,
    tenant_id: UUID,
) -> str | None:
    """Purge all R2 export objects for the tenant.

    Deletes all export artifacts (current, previous, partial uploads).
    Returns ``None`` on success, or an error message on failure.
    """
    jobs = await export_jobs_repository.get_all_for_tenant(db, tenant_id)
    keys_to_delete: set[str] = set()

    for job in jobs:
        if job.r2_key:
            keys_to_delete.add(job.r2_key)

    if not keys_to_delete:
        return None

    storage = export_service.get_storage()
    for key in keys_to_delete:
        try:
            await storage.delete(key)
        except (StorageObjectNotFoundError, StorageOperationError) as exc:
            logger.warning(
                "Failed to purge export object %s tenant=%s: %s",
                key,
                tenant_id,
                exc,
            )
            return "Could not remove stored export data. Please try again."

    return None


async def _delete_evolution_instance(profile: Tenant) -> str | None:
    """Delete the Evolution instance for the tenant (idempotent).

    Returns ``None`` on success, or an error message on failure.
    """
    instance_name = profile.evolution_instance_name
    if not instance_name:
        return None

    try:
        await evolution_client.delete_instance(instance_name)
    except Exception as exc:
        logger.warning(
            "Failed to delete Evolution instance %s tenant=%s: %s",
            instance_name,
            profile.id,
            exc,
        )
        return "Could not remove WhatsApp instance. Please try again."

    return None


async def _cleanup_redis_sessions(profile: Tenant) -> None:
    """Best-effort cleanup of Redis WhatsApp sessions.

    Keys expire after 5 minutes anyway, so this is best-effort with
    safe logging (no PII in logs).
    """
    phone = profile.whatsapp_phone
    if not phone:
        return

    try:
        from app.core.redis_client import get_redis_manager

        manager = get_redis_manager()
        if manager is None:
            return

        async def _clean(client):
            await client.delete(f"session:admin:{phone}")

        await manager.execute("cleanup_on_deletion", _clean)
    except Exception:
        logger.warning(
            "Best-effort Redis session cleanup failed tenant=%s",
            profile.id,
            exc_info=True,
        )


async def delete_tenant_as_master(
    db: AsyncSession,
    tenant_id: UUID,
    master_user: User,
    password: str,
    destructive_word: str,
    locale: str,
    limiter: StepUpRateLimiter | None,
) -> dict:
    """Permanently delete an inactive Tenant as Master.

    Args:
        db: Database session.
        tenant_id: The tenant to delete.
        master_user: The Master requesting deletion.
        password: Current Master password for step-up authentication.
        destructive_word: Locale-aware destructive word (DELETE/ELIMINAR).
        locale: Master locale for destructive word validation.
        limiter: Step-up rate limiter (may be None if Redis unavailable).

    Returns:
        A dict with ``success: True`` on completion.

    Raises:
        ValueError: Validation errors (active tenant, wrong word, etc.)
        StepUpError: Rate limit exceeded for password attempts.
        RuntimeError: External cleanup failures that preserve the tenant.
    """
    # ── 1. Load tenant with owner ──────────────────────────────
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.owner)).where(Tenant.id == tenant_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        raise ValueError("Tenant not found")

    if profile.is_active:
        raise ValueError("Cannot delete active tenant. Deactivate first.")

    owner_user: User = profile.owner  # type: ignore[assignment]
    actor_user_id = master_user.id

    # ── 2. Step-up authentication ─────────────────────────────
    if limiter is not None:
        try:
            await limiter.check(str(actor_user_id))
        except StepUpError as exc:
            raise StepUpError(str(exc)) from exc

    if not verify_password(password, master_user.password_hash):
        if limiter is not None:
            try:
                await limiter.record_failure(str(actor_user_id))
            except StepUpError:
                pass
        raise ValueError("Invalid password or confirmation word")

    if not await _validate_destructive_word(destructive_word, locale):
        if limiter is not None:
            try:
                await limiter.record_failure(str(actor_user_id))
            except StepUpError:
                pass
        raise ValueError("Invalid password or confirmation word")

    if limiter is not None:
        try:
            await limiter.record_success(str(actor_user_id))
        except StepUpError:
            pass

    logger.info(
        "Master tenant deletion initiated actor=%s tenant=%s",
        actor_user_id,
        tenant_id,
    )

    # ── 3. Cancel in-progress export (wait up to 30s) ─────────
    cancel_ok, cancel_err = await _cancel_export_and_wait(
        db,
        tenant_id,
        actor_user_id,
    )
    if not cancel_ok:
        raise RuntimeError(cancel_err or "Export cancellation timed out. Try again.")

    # ── 4. Purge R2 objects (fail-closed) ─────────────────────
    r2_err = await _purge_export_storage(db, tenant_id)
    if r2_err:
        raise RuntimeError(r2_err)

    # ── 5. Delete Evolution instance (idempotent, fail-closed) ─
    evo_err = await _delete_evolution_instance(profile)
    if evo_err:
        raise RuntimeError(evo_err)

    # ── 6. Best-effort Redis session cleanup ──────────────────
    await _cleanup_redis_sessions(profile)

    # ── 7. Database deletion ──────────────────────────────────
    # Purge export jobs explicitly (FK cascade works in PostgreSQL
    # but SQLite tests need this before the cascade).
    await export_jobs_repository.purge_tenant_jobs(db, tenant_id)

    # Delete all client users for this tenant explicitly since
    # Client -> User has no ORM cascade and SQLite doesn't enforce
    # FK cascades.
    clients = await db.execute(
        select(ClientModel).where(ClientModel.tenant_id == tenant_id)
    )
    for client in clients.scalars().all():
        if client.owner_user_id != actor_user_id:
            user_to_delete = await db.get(User, client.owner_user_id)
            if user_to_delete is not None:
                await db.delete(user_to_delete)

    # Delete the owner User — this cascade-deletes the Tenant (via
    # owned_tenant relationship) and the Tenant cascade-deletes all
    # owned records (Clients, Services, Plans, Settings,
    # Mailbox, etc.) via FK ondelete=CASCADE.
    previous_context = get_rls_context(db)
    try:
        await sessions_repository.revoke_all_for_user(db, owner_user.id)
        await db.flush()
        await db.delete(owner_user)
        await db.flush()
    finally:
        if previous_context is not None:
            await set_rls_context(
                db,
                previous_context["user_id"],
                previous_context["role"],
                previous_context["active_tenant_id"],
            )

    # ── 8. Commit final ───────────────────────────────────────
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error(
            "Final database commit failed after external cleanup tenant=%s: %s",
            tenant_id,
            exc,
        )
        raise RuntimeError(
            "Account deletion could not be finalised. "
            "Please try again \u2014 external resources have been cleaned up."
        ) from exc

    await restore_rls_context(db)

    logger.info(
        "Master tenant deletion succeeded actor=%s tenant=%s",
        actor_user_id,
        tenant_id,
    )

    return {"success": True}


async def delete_tenant_account(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: UUID,
    password: str,
    destructive_word: str,
    locale: str,
    limiter: StepUpRateLimiter | None,
) -> dict:
    """Permanently delete the active Tenant and all owned data.

    This is the main orchestration function for Tenant Admin self-service
    deletion.

    Args:
        db: Database session.
        tenant_id: The tenant to delete.
        actor_user_id: The user requesting deletion (must be the tenant owner).
        password: Current password for step-up authentication.
        destructive_word: Locale-aware destructive word (DELETE/ELIMINAR).
        locale: Account locale for destructive word validation.
        limiter: Step-up rate limiter (may be None if Redis unavailable).

    Returns:
        A dict with ``success: True`` on completion.

    Raises:
        ValueError: Validation errors (wrong word, wrong actor, etc.)
        StepUpError: Rate limit exceeded for password attempts.
        RuntimeError: External cleanup failures that preserve the tenant.
    """
    # ── 1. Load tenant with owner ──────────────────────────────
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.owner)).where(Tenant.id == tenant_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        raise ValueError("Tenant not found")

    if profile.owner_user_id != actor_user_id:
        raise ValueError("Only the owning Tenant Admin can delete this account")

    if not profile.is_active:
        raise ValueError("Account is already deactivated. Contact Master support.")

    owner_user: User = profile.owner  # type: ignore[assignment]

    # ── 2. Step-up authentication ─────────────────────────────
    if limiter is not None:
        try:
            await limiter.check(str(actor_user_id))
        except StepUpError as exc:
            raise StepUpError(str(exc)) from exc

    if not verify_password(password, owner_user.password_hash):
        if limiter is not None:
            try:
                await limiter.record_failure(str(actor_user_id))
            except StepUpError:
                pass
        raise ValueError("Invalid password or confirmation word")

    if not await _validate_destructive_word(destructive_word, locale):
        if limiter is not None:
            try:
                await limiter.record_failure(str(actor_user_id))
            except StepUpError:
                pass
        raise ValueError("Invalid password or confirmation word")

    if limiter is not None:
        try:
            await limiter.record_success(str(actor_user_id))
        except StepUpError:
            pass

    logger.info(
        "Tenant deletion initiated actor=%s tenant=%s",
        actor_user_id,
        tenant_id,
    )

    # ── 3. Cancel in-progress export (wait up to 30s) ─────────
    cancel_ok, cancel_err = await _cancel_export_and_wait(
        db,
        tenant_id,
        actor_user_id,
    )
    if not cancel_ok:
        raise RuntimeError(cancel_err or "Export cancellation timed out. Try again.")

    # ── 4. Purge R2 objects (fail-closed) ─────────────────────
    r2_err = await _purge_export_storage(db, tenant_id)
    if r2_err:
        raise RuntimeError(r2_err)

    # ── 5. Delete Evolution instance (idempotent, fail-closed) ─
    evo_err = await _delete_evolution_instance(profile)
    if evo_err:
        raise RuntimeError(evo_err)

    # ── 6. Best-effort Redis session cleanup ──────────────────
    await _cleanup_redis_sessions(profile)

    # ── 7. Database deletion ──────────────────────────────────
    # Purge export jobs explicitly (FK cascade works in PostgreSQL
    # but SQLite tests need this before the cascade).
    await export_jobs_repository.purge_tenant_jobs(db, tenant_id)

    # Delete all client users for this tenant explicitly since
    # Client -> User has no ORM cascade and SQLite doesn't enforce
    # FK cascades.
    clients = await db.execute(
        select(ClientModel).where(ClientModel.tenant_id == tenant_id)
    )
    for client in clients.scalars().all():
        if client.owner_user_id != actor_user_id:
            user_to_delete = await db.get(User, client.owner_user_id)
            if user_to_delete is not None:
                await db.delete(user_to_delete)

    # Delete the owner User — this cascade-deletes the Tenant (via
    # owned_tenant relationship) and the Tenant cascade-deletes all
    # owned records (Clients, Services, Plans, Settings,
    # Mailbox, etc.) via FK ondelete=CASCADE.
    previous_context = get_rls_context(db)
    try:
        await sessions_repository.revoke_all_for_user(db, actor_user_id)
        await db.flush()
        await db.delete(owner_user)
        await db.flush()
    finally:
        if previous_context is not None:
            await set_rls_context(
                db,
                previous_context["user_id"],
                previous_context["role"],
                previous_context["active_tenant_id"],
            )

    # ── 8. Commit final ───────────────────────────────────────
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error(
            "Final database commit failed after external cleanup tenant=%s: %s",
            tenant_id,
            exc,
        )
        raise RuntimeError(
            "Account deletion could not be finalised. "
            "Please try again — external resources have been cleaned up."
        ) from exc

    await restore_rls_context(db)

    logger.info(
        "Tenant deleted successfully actor=%s tenant=%s",
        actor_user_id,
        tenant_id,
    )

    return {"success": True}


__all__ = [
    "delete_tenant_account",
    "delete_tenant_as_master",
    "CANCEL_WAIT_SECONDS",
]
