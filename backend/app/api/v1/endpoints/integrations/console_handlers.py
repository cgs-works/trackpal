"""WhatsApp console handlers for master, tenant, and client roles.

Functions are called from ``console.py`` after instance-first routing
has resolved the caller's identity/role.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import RedisUnavailableError, get_redis_manager
from app.repositories import (
    mailbox_config_repository,
    mailbox_lookup_repository,
    tenants_repository,
)
from app.schemas.whatsapp import WhatsAppConsoleResponse
from app.services.mail_lookup_worker import enqueue_job
from app.services.auth_service import AuthService
from app.services.catalog_service import CatalogService
from app.services.client_service import ClientService
from app.services.contingency_reply_policy import ContingencyReplyPolicy

from app.services.profile_service import ProfileService
from app.services.subscription_service import SubscriptionService
from app.services.tenant_service import TenantService
from app.services.whatsapp_auth_session_service import WhatsAppAuthSessionService
from app.services.whatsapp_client_console_facade import WhatsAppClientConsoleFacade
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_master_console_facade import WhatsAppMasterConsoleFacade
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.whatsapp_tenant_console_facade import WhatsAppTenantConsoleFacade
from app.services.whatsapp_tenant_console_service import WhatsAppTenantConsoleService
from app.api.v1.endpoints.integrations.adapter import (
    _TenantConsoleAdapter,
    UNKNOWN_PHONE_REPLY,
)

logger = logging.getLogger(__name__)

auth_service = AuthService()
console_service = WhatsAppConsoleService()
tenant_service = TenantService()

CONSOLE_STATE_UNAVAILABLE_REPLY = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE

# ====================================================================
# Master console handler
# ====================================================================


async def _handle_master_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle message from identified Master user."""
    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    auth_session_service = WhatsAppAuthSessionService(
        connection_manager=manager,
        session_ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        fail_threshold=settings.whatsapp_auth_fail_threshold,
        lock_minutes=settings.whatsapp_auth_lock_minutes,
        fail_window_minutes=settings.whatsapp_auth_fail_window_minutes,
    )

    adapter = _TenantConsoleAdapter(tenant_service, db)
    facade = WhatsAppMasterConsoleFacade(
        console_service=console_service,
        session_service=session_service,
        auth_session_service=auth_session_service,
        tenant_service=adapter,
    )

    try:
        reply = await facade.process_message(
            phone=phone,
            message=message,
            instance=instance,
            db=db,
        )
    except (RedisUnavailableError, ConnectionError, TimeoutError, OSError):
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)
    return WhatsAppConsoleResponse(reply=reply)


# ====================================================================
# Tenant console handler
# ====================================================================


async def _handle_tenant_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
) -> WhatsAppConsoleResponse:
    """Handle message from identified Tenant Admin user."""
    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    tenant_console_service = WhatsAppTenantConsoleService(
        client_service=ClientService(),
        catalog_service=CatalogService(),
        profile_service=ProfileService(),
        subscription_service=SubscriptionService(),
    )

    facade = WhatsAppTenantConsoleFacade(
        console_service=tenant_console_service,
        session_service=session_service,
        tenant_service=TenantService(),
    )

    identity = await auth_service.identify_by_phone(db, phone)
    if identity is None:
        return WhatsAppConsoleResponse(reply=UNKNOWN_PHONE_REPLY)

    try:
        reply = await facade.process_message(
            phone=phone,
            message=message,
            identity=identity,
            instance=instance,
            db=db,
        )
    except (RedisUnavailableError, ConnectionError, TimeoutError, OSError):
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    # === Lookup job orchestration (for codigo flow intent) ===
    lookup_job_id: str | None = None
    tenant_id_out: str | None = None
    session = None

    try:
        session = await session_service.get_session(f"admin:{phone}")
        has_lookup_intent = (
            session is not None
            and session.temp_data.get("pending_lookup_intent") == "true"
        )
        if has_lookup_intent:
            assert session is not None
            pending_service_key = session.temp_data.get("service_key")
            pending_target_email = session.temp_data.get("target_email")

            if (
                pending_service_key
                and pending_target_email
                and identity is not None
                and identity.get("role") == "tenant"
            ):
                tenant = await tenants_repository.get_by_owner(db, identity["user_id"])
                if tenant is not None:
                    mailbox = await mailbox_config_repository.get_by_tenant(
                        db, tenant.id
                    )
                    if mailbox is not None and mailbox.status == "connected":
                        job = await mailbox_lookup_repository.create_job(
                            db,
                            tenant_id=tenant.id,
                            mailbox_id=mailbox.id,
                            service_key=pending_service_key,
                            target_email=pending_target_email,
                        )
                        await db.flush()
                        await db.commit()

                        redis_manager = get_redis_manager()
                        try:
                            enqueued = (
                                await enqueue_job(redis_manager, job.id)
                                if redis_manager is not None
                                else False
                            )
                        except Exception:
                            logger.exception(
                                "Failed to enqueue lookup job %s for tenant %s",
                                job.id,
                                tenant.id,
                            )
                            enqueued = False

                        if enqueued:
                            lookup_job_id = str(job.id)
                            tenant_id_out = str(tenant.id)
                            session.temp_data.pop("pending_lookup_intent", None)
                            session.temp_data.pop("service_key", None)
                            session.temp_data.pop("target_email", None)
                            await session_service.save_session(session, touch_ttl=False)
                        else:
                            reply = tenant_console_service._t(
                                tenant_console_service.KEY_CODIGO_ERROR
                            )
                            logger.warning(
                                "Compensating: deleting job %s after enqueue "
                                "failure for tenant %s",
                                job.id,
                                tenant.id,
                            )
                            try:
                                await db.delete(job)
                                await db.commit()
                            except Exception:
                                logger.critical(
                                    "Job %s created but enqueue failed AND "
                                    "compensating delete failed. Marking failed.",
                                    job.id,
                                )
                                try:
                                    await db.rollback()
                                    await mailbox_lookup_repository.transition_status(
                                        db,
                                        job,
                                        "failed",
                                        error_code="queue_unavailable",
                                        error_detail_safe=(
                                            "Queue processing unavailable"
                                        ),
                                    )
                                    await db.commit()
                                except Exception:
                                    logger.exception(
                                        "Failed to mark job %s as failed",
                                        job.id,
                                    )
                    else:
                        reply = tenant_console_service._t(
                            tenant_console_service.KEY_CODIGO_ERROR
                        )
                        logger.warning(
                            "No connected mailbox for tenant %s; keeping lookup intent",
                            tenant.id,
                        )
    except Exception:
        logger.exception("Failed to orchestrate lookup job for phone=%s", phone)
        if (
            session is not None
            and session.temp_data.get("pending_lookup_intent") == "true"
        ):
            reply = tenant_console_service._t(tenant_console_service.KEY_CODIGO_ERROR)

    return WhatsAppConsoleResponse(
        reply=reply,
        lookup_job_id=lookup_job_id,
        tenant_id=tenant_id_out,
    )


# ====================================================================
# Client console handler
# ====================================================================


async def _handle_client_console(
    phone: str,
    message: str,
    instance: str | None,
    manager: object,
    db: AsyncSession,
    identity: dict,
    locale: str = "es",
) -> WhatsAppConsoleResponse:
    """Handle message from identified Client user."""
    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    facade = WhatsAppClientConsoleFacade(
        session_service=session_service,
        locale=locale,
    )

    exit_cmd = message.strip().lower() in ("0", "salir")

    try:
        reply = await facade.process_message(
            phone=phone,
            message=message,
            identity=identity,
            instance=instance,
            db=db,
        )
    except (RedisUnavailableError, ConnectionError, TimeoutError, OSError):
        return WhatsAppConsoleResponse(reply=CONSOLE_STATE_UNAVAILABLE_REPLY)

    resp = WhatsAppConsoleResponse(reply=reply)
    if exit_cmd:
        resp.status = "closed"
    return resp
