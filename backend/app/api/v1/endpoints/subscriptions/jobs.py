import uuid
from typing import Optional

from fastapi import HTTPException, status

from app.api.dependencies import ApiKeyDbDep
from app.core.i18n import t as _t
from app.schemas.subscription import MarkFailedRequest, ReminderPendingResponse
from app.services.subscription_job_service import SubscriptionJobService
from app.api.v1.endpoints.subscriptions.router import jobs_router, reminders_router

subscription_job_service = SubscriptionJobService()


@jobs_router.post("/jobs")
async def run_subscription_job(
    db: ApiKeyDbDep,
    task: str = "cleanup",
):
    """Run a subscription lifecycle job.

    Protected by ``N8N_API_KEY`` header.  Supported tasks:
    - ``cleanup``: expire/cancel/delete lifecycle transitions.
    - ``reminders``: placeholder (separate TODO).
    - ``all``: run both.

    Returns per-item results with IDs, action, status, and optional error.
    No PII or secrets are returned.
    """
    if task not in ("cleanup", "reminders", "all"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task '{task}'. Must be one of: cleanup, reminders, all",
        )

    results: list[dict] = []

    if task in ("cleanup", "all"):
        cleanup_results = await subscription_job_service.run_cleanup(db)
        results.extend(cleanup_results)

    if task in ("reminders", "all"):
        reminder_results = await subscription_job_service.run_reminders_stub()
        results.extend(reminder_results)

    return {"task": task, "items_processed": len(results), "results": results}


@reminders_router.post("/pending", response_model=ReminderPendingResponse)
async def get_pending_reminders(
    db: ApiKeyDbDep,
    cursor: Optional[str] = None,
    page_size: int = 100,
):
    """Generate and return pending reminder payloads.

    Protected by ``N8N_API_KEY`` header.  Returns at most ``page_size``
    payloads (default 100).  If more pages exist, includes an opaque
    ``next_cursor``.
    """
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_size must be between 1 and 100",
        )
    result = await subscription_job_service.generate_reminder_payloads(
        db, cursor=cursor, page_size=page_size
    )
    return result


@reminders_router.post("/{log_id}/mark-sent")
async def mark_reminder_sent(
    db: ApiKeyDbDep,
    log_id: uuid.UUID,
):
    """Mark a reminder log as sent after n8n confirms Evolution success."""
    locale = "en"  # API-key flow; no tenant context to resolve locale
    result = await subscription_job_service.mark_reminder_sent(db, log_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.reminder_log_not_found"),
        )
    return result


@reminders_router.post("/{log_id}/mark-failed")
async def mark_reminder_failed(
    db: ApiKeyDbDep,
    log_id: uuid.UUID,
    payload: MarkFailedRequest,
):
    """Mark a reminder log as failed after Evolution send failure.

    Retries up to 3 attempts before setting permanent ``failed`` status.
    """
    locale = "en"  # API-key flow; no tenant context to resolve locale
    result = await subscription_job_service.mark_reminder_failed(
        db, log_id, reason=payload.reason
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.reminder_log_not_found"),
        )
    return result
