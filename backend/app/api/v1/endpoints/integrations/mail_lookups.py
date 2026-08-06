"""n8n lookup job endpoints — create job and poll status.

Contract
--------
``POST /n8n/mail/lookups``
  Input: ``{service_key, target_email, tenant_instance?}``
  Output: ``{job_id, status: "pending"}``

``GET /n8n/mail/lookups/{job_id}``
  Output: ``{job_id, status, result_type?, result_value?, reply?,
            error_code?, error_detail?, created_at?, completed_at?}``

The ``result_value`` is ephemeral (not persisted in DB) and available
for a short window after job completion.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import ApiKeyDbDep
from app.core.config import settings
from app.core.demo_guardrail import DemoGuardrailError, assert_demo_operation_allowed
from app.core.metrics import metrics
from app.repositories import mailbox_config_repository, mailbox_lookup_repository
from app.repositories import tenants_repository
from app.schemas.mailbox import (
    LookupCreateRequest,
    LookupCreateResponse,
    LookupResumeRequest,
    LookupStatusResponse,
)
from app.services.lookup_execution_coordinator import get_lookup_execution_coordinator
from app.services.lookup_execution_coordinator.coordinator import (
    lookup_response_deadline_expired,
)
from app.services.lookup_execution_coordinator.replies import render_lookup_reply

logger = logging.getLogger(__name__)

router = APIRouter(tags=["integrations"])


def _is_allowed_resume_url(value: str) -> bool:
    """Allow only HTTPS Wait URLs on the configured n8n origin."""
    allowed = urlsplit(settings.n8n_resume_allowed_origin)
    candidate = urlsplit(value)
    return (
        allowed.scheme == "https"
        and candidate.scheme == "https"
        and allowed.netloc
        and candidate.netloc == allowed.netloc
        and candidate.username is None
        and candidate.password is None
    )


async def _status_response(
    job, coordinator=None, *, locale: str
) -> LookupStatusResponse:
    """Build one job response, including an ephemeral result when available."""
    response = LookupStatusResponse(
        job_id=job.id,
        status=job.status,
        result_type=job.result_type,
        error_code=job.error_code,
        error_detail=job.error_detail_safe,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
    if job.status == "completed" and job.result_type in ("code", "url"):
        cached = None
        if coordinator is not None:
            try:
                cached = await coordinator.get_result(job.id)
            except Exception:
                logger.exception(
                    "Could not read ephemeral result for lookup job %s", job.id
                )
        if cached is not None:
            response.result_type = cached[0]
            response.result_value = cached[1]
        else:
            response.status = "failed"
            response.result_type = None
            response.error_code = "result_unavailable"
            response.error_detail = "Lookup result is no longer available"
    response.reply = render_lookup_reply(
        locale,
        status=response.status,
        result_type=response.result_type,
        result_value=response.result_value,
        error_code=response.error_code,
        service_key=job.service_key,
    )
    return response


@router.post(
    "/n8n/mail/lookups",
    response_model=LookupCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lookup(
    payload: LookupCreateRequest,
    db: ApiKeyDbDep,
):
    """Create a new mail lookup job.

    Identifies the tenant via ``tenant_instance`` (Evolution instance
    name) or ``tenant_id``. Creates and commits a ``pending`` job,
    schedules it through the execution coordinator, and returns the
    ``job_id`` for polling.
    """
    # 1. Resolve tenant
    tenant = None
    if payload.tenant_id:
        tenant = await tenants_repository.get(db, payload.tenant_id)
    elif payload.tenant_instance:
        tenant = await tenants_repository.get_by_instance(db, payload.tenant_instance)

    if tenant is None:
        metrics.inc(
            "lookup_api_create", status="tenant_not_found", service=payload.service_key
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    try:
        assert_demo_operation_allowed(tenant, operation="n8n_mail_lookup")
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.code,
        ) from exc
    if not tenant.is_active:
        metrics.inc(
            "lookup_api_create", status="tenant_inactive", service=payload.service_key
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant is not active",
        )

    # 2. Validate required target_email
    if not payload.target_email or len(payload.target_email.strip()) < 3:
        metrics.inc(
            "lookup_api_create",
            status="missing_target_email",
            service=payload.service_key,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_email is required and must be a valid email",
        )

    # 3. Look up mailbox
    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant.id)
    if mailbox is None:
        metrics.inc(
            "lookup_api_create", status="no_mailbox", service=payload.service_key
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant has no mailbox configured",
        )
    if mailbox.status != "connected":
        metrics.inc(
            "lookup_api_create",
            status="bad_mailbox_status",
            service=payload.service_key,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mailbox status is '{mailbox.status}'; must be 'connected'",
        )

    # 4. Create job
    job = await mailbox_lookup_repository.create_job(
        db,
        tenant_id=tenant.id,
        mailbox_id=mailbox.id,
        service_key=payload.service_key,
        target_email=payload.target_email,
    )
    await db.flush()
    await db.commit()

    # 5. Schedule through the durable execution coordinator (best-effort).
    # PostgreSQL is authoritative once the job commit succeeds; polling can
    # recover a dispatch that was unavailable at creation time.
    try:
        await get_lookup_execution_coordinator().schedule(job.id)
    except Exception:
        logger.exception(
            "Job %s created but could not be scheduled immediately", job.id
        )
    metrics.inc("lookup_api_create", status="ok", service=payload.service_key)
    return LookupCreateResponse(
        job_id=job.id,
        status="pending",
    )


@router.post(
    "/n8n/mail/lookups/{job_id}/resume",
    response_model=LookupStatusResponse,
)
async def register_lookup_resume(
    job_id: UUID,
    payload: LookupResumeRequest,
    db: ApiKeyDbDep,
):
    """Register the unique n8n Wait resume URL for one tenant job."""
    job = await mailbox_lookup_repository.get_job(
        db, job_id, tenant_id=payload.tenant_id
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    if not _is_allowed_resume_url(payload.resume_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid resume URL",
        )

    coordinator = get_lookup_execution_coordinator()
    if job.status in {"pending", "processing"}:
        await coordinator.register_resume_url(job.id, payload.resume_url)
        await db.refresh(job)
    locale = await tenants_repository.resolve_locale(db, job.tenant_id)
    return await _status_response(job, coordinator, locale=locale)


@router.get(
    "/n8n/mail/lookups/{job_id}",
    response_model=LookupStatusResponse,
)
async def get_lookup_status(
    job_id: UUID,
    db: ApiKeyDbDep,
    tenant_id: UUID = Query(
        ...,
        description="Required tenant ID — scopes job lookup to tenant, preventing cross-tenant job_id guessing",
    ),
):
    """Poll a lookup job's status and result.

    Tenant ownership is enforced — ``tenant_id`` is required and must
    match the job's tenant, preventing cross-tenant ``job_id``
    guessing. ``result_value`` is read from the coordinator's ephemeral
    Redis result store (not persisted in DB).
    """
    tenant = await tenants_repository.get(db, tenant_id)
    if tenant is not None:
        try:
            assert_demo_operation_allowed(tenant, operation="n8n_mail_lookup_poll")
        except DemoGuardrailError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=exc.code,
            ) from exc
    job = await mailbox_lookup_repository.get_job(db, job_id, tenant_id=tenant_id)
    if job is None:
        metrics.inc("lookup_api_poll", status="job_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    try:
        coordinator = get_lookup_execution_coordinator()
    except RuntimeError:
        coordinator = None

    if job.status in {"pending", "processing"} and lookup_response_deadline_expired(
        job
    ):
        locked_job = await mailbox_lookup_repository.get_job(
            db,
            job_id,
            tenant_id=tenant_id,
            with_for_update=True,
        )
        if locked_job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )
        job = locked_job
        timed_out = False
        if job.status in {
            "pending",
            "processing",
        } and lookup_response_deadline_expired(job):
            await mailbox_lookup_repository.transition_status(
                db,
                job,
                "timeout",
                error_code="lookup_timeout",
                error_detail_safe="Interactive lookup deadline expired",
            )
            timed_out = True
        await db.commit()
        if timed_out and coordinator is not None:
            await coordinator.release_job_lease(job.id)
    elif (
        coordinator is not None
        and job.status == "pending"
        and job.expires_at is not None
    ):
        expires_at = job.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at > datetime.now(timezone.utc):
            try:
                await coordinator.schedule(job.id)
            except Exception:
                logger.exception("Could not reschedule pending lookup job %s", job.id)

    locale = await tenants_repository.resolve_locale(db, job.tenant_id)
    try:
        response = await _status_response(job, coordinator, locale=locale)
    except Exception:
        logger.exception("Could not read lookup result for job %s", job.id)
        response = LookupStatusResponse(
            job_id=job.id,
            status=job.status,
            result_type=job.result_type,
            error_code=job.error_code,
            error_detail=job.error_detail_safe,
            reply=render_lookup_reply(
                locale,
                status=job.status,
                result_type=job.result_type,
                result_value=None,
                error_code=job.error_code,
                service_key=job.service_key,
            ),
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    metrics.inc("lookup_api_poll", status=job.status)
    return response
