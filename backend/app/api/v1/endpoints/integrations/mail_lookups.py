"""n8n lookup job endpoints — create job and poll status.

Contract
--------
``POST /n8n/mail/lookups``
  Input: ``{service_key, target_email, tenant_instance?}``
  Output: ``{job_id, status: "pending"}``

``GET /n8n/mail/lookups/{job_id}``
  Output: ``{job_id, status, result_type?, result_value?,
            error_code?, error_detail?, created_at?, completed_at?}``

The ``result_value`` is ephemeral (not persisted in DB) and available
for a short window after job completion.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import ApiKeyDbDep
from app.core.metrics import metrics
from app.core.redis_client import get_redis_manager
from app.repositories import mailbox_config_repository, mailbox_lookup_repository
from app.repositories import tenants_repository
from app.schemas.mailbox import (
    LookupCreateRequest,
    LookupCreateResponse,
    LookupStatusResponse,
)
from app.services.mail_lookup_worker import enqueue_job, get_ephemeral_result

logger = logging.getLogger(__name__)

router = APIRouter(tags=["integrations"])


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
    name) or ``tenant_id``.  Creates a ``pending`` job, enqueues it
    on Redis, and returns the ``job_id`` for polling.
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
    if mailbox.status not in ("connected", "error"):
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

    # 5. Enqueue to Redis (best-effort)
    manager = get_redis_manager()
    enqueued = await enqueue_job(manager, job.id)
    if not enqueued:
        logger.warning("Job %s created but not enqueued (Redis unavailable)", job.id)

    await db.commit()
    metrics.inc("lookup_api_create", status="ok", service=payload.service_key)
    return LookupCreateResponse(
        job_id=job.id,
        status="pending",
    )


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
    guessing.  ``result_value`` is returned from the ephemeral cache
    (not persisted in DB).
    """
    job = await mailbox_lookup_repository.get_job(db, job_id, tenant_id=tenant_id)
    if job is None:
        metrics.inc("lookup_api_poll", status="job_not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Build response
    resp = LookupStatusResponse(
        job_id=job.id,
        status=job.status,
        result_type=job.result_type,
        error_code=job.error_code,
        error_detail=job.error_detail_safe,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )

    # Add ephemeral result_value if job is completed with a find
    if job.status == "completed" and job.result_type in ("code", "url"):
        cached = get_ephemeral_result(job.id)
        if cached is not None:
            resp.result_type = cached[0]
            resp.result_value = cached[1]

    metrics.inc("lookup_api_poll", status=job.status)
    return resp
