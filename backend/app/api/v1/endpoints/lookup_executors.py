"""Master-only API for external lookup executor lifecycle management."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import DbDep, MasterUser
from app.models import LookupExecutor
from app.repositories import lookup_executors_repository
from app.schemas.lookup_executors import (
    LookupExecutorCreateRequest,
    LookupExecutorCreateResponse,
    LookupExecutorResponse,
    LookupExecutorUpdateRequest,
)
from app.services import export_service
from app.services.lookup_executor_registry import (
    ExecutorCoordinationUnavailable,
    ExecutorVerificationError,
    create_executor,
    delete_executor,
    reveal_hosting_password,
    rotate_secret,
    test_executor,
    verify_executor,
)
from app.services.master_step_up import MasterStepUpError, verify_master_step_up

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lookup-executors", tags=["lookup-executors"])


class VerifyExecutorRequest(BaseModel):
    """Confirmation and optional step-up password for activation."""

    confirmation: str | None = None
    password: str | None = None


class MasterPasswordRequest(BaseModel):
    """Master password step-up payload."""

    password: str


class HostingPasswordResponse(BaseModel):
    """Sensitive response returned only by the explicit reveal endpoint."""

    hosting_account_password: str


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="executor_not_found")


def _step_up_error(exc: MasterStepUpError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.code)


async def _get_executor(db: DbDep, executor_id: UUID) -> LookupExecutor:
    executor = await lookup_executors_repository.get(db, executor_id)
    if executor is None:
        raise _not_found()
    return executor


@router.post(
    "/",
    response_model=LookupExecutorCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lookup_executor(
    body: LookupExecutorCreateRequest,
    db: DbDep,
    current_user: MasterUser,
) -> LookupExecutorCreateResponse:
    """Create a draft and return its protocol secret once."""
    del current_user
    executor, plain_secret = await create_executor(db, **body.model_dump())
    await db.commit()
    await db.refresh(executor)
    return LookupExecutorCreateResponse(executor=executor, plain_secret=plain_secret)


@router.get("/", response_model=list[LookupExecutorResponse])
async def list_lookup_executors(
    db: DbDep, current_user: MasterUser
) -> list[LookupExecutorResponse]:
    """List executor metadata without credential values."""
    del current_user
    return await lookup_executors_repository.list_all(db)


@router.get("/{executor_id}", response_model=LookupExecutorResponse)
async def get_lookup_executor(
    executor_id: UUID, db: DbDep, current_user: MasterUser
) -> LookupExecutorResponse:
    """Return one executor without credential values."""
    del current_user
    return await _get_executor(db, executor_id)


@router.put("/{executor_id}", response_model=LookupExecutorResponse)
async def update_lookup_executor(
    executor_id: UUID,
    body: LookupExecutorUpdateRequest,
    db: DbDep,
    current_user: MasterUser,
) -> LookupExecutorResponse:
    """Update executor metadata and quarantine destination changes."""
    del current_user
    executor = await _get_executor(db, executor_id)
    fields = body.model_dump(exclude_unset=True)
    destination_changed = any(
        field in fields and fields[field] != getattr(executor, field)
        for field in ("base_url", "transport_mode")
    )
    await lookup_executors_repository.update(db, executor, **fields)
    if destination_changed:
        executor.requires_reverification = True
        executor.last_verified_at = None
        if executor.lifecycle_status == "active":
            executor.lifecycle_status = "disabled"
        await lookup_executors_repository.update_health(
            db, executor, "unknown", "executor configuration changed"
        )
    await db.commit()
    await db.refresh(executor)
    return executor


@router.post("/{executor_id}/verify", response_model=LookupExecutorResponse)
async def verify_lookup_executor(
    executor_id: UUID,
    db: DbDep,
    current_user: MasterUser,
    body: VerifyExecutorRequest | None = None,
) -> LookupExecutorResponse:
    """Challenge the executor and activate or promote its current key."""
    executor = await _get_executor(db, executor_id)
    confirmation = body.confirmation if body else None
    if executor.transport_mode == "http_encrypted":
        if confirmation != "ALLOW HTTP":
            raise HTTPException(
                status_code=400, detail="insecure_http_confirmation_required"
            )
        if body is None or body.password is None:
            raise HTTPException(status_code=401, detail="invalid_master_password")
        try:
            await verify_master_step_up(
                db, current_user, body.password, export_service.get_limiter()
            )
        except MasterStepUpError as exc:
            raise _step_up_error(exc) from exc
    try:
        await verify_executor(db, executor, confirmation)
    except ValueError as exc:
        if str(exc) == "insecure_http_confirmation_required":
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise
    except ExecutorVerificationError as exc:
        await db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(executor)
    return executor


@router.post("/{executor_id}/test")
async def test_lookup_executor(
    executor_id: UUID, db: DbDep, current_user: MasterUser
) -> dict[str, object]:
    """Check executor connectivity without establishing verification state."""
    del current_user
    executor = await _get_executor(db, executor_id)
    try:
        challenge = await test_executor(db, executor)
    except ExecutorVerificationError as exc:
        await db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(executor)
    return {
        "status": "healthy",
        "protocol_version": challenge.protocol_version,
        "runtime_version": challenge.runtime_version,
        "max_concurrency": challenge.max_concurrency,
        "executor": LookupExecutorResponse.model_validate(executor).model_dump(),
    }


async def _set_lifecycle(
    executor_id: UUID, db: DbDep, current_user: MasterUser, lifecycle: str
) -> LookupExecutorResponse:
    del current_user
    executor = await _get_executor(db, executor_id)
    if lifecycle == "active" and (
        executor.requires_reverification
        or executor.health_status != "healthy"
        or executor.last_verified_at is None
    ):
        raise HTTPException(status_code=409, detail="executor_requires_verification")
    await lookup_executors_repository.update_lifecycle_status(db, executor, lifecycle)
    await db.commit()
    await db.refresh(executor)
    return executor


@router.post("/{executor_id}/enable", response_model=LookupExecutorResponse)
async def enable_lookup_executor(
    executor_id: UUID, db: DbDep, current_user: MasterUser
) -> LookupExecutorResponse:
    """Enable an executor only after a successful verification challenge."""
    return await _set_lifecycle(executor_id, db, current_user, "active")


@router.post("/{executor_id}/disable", response_model=LookupExecutorResponse)
async def disable_lookup_executor(
    executor_id: UUID, db: DbDep, current_user: MasterUser
) -> LookupExecutorResponse:
    """Disable an executor without deleting its encrypted credentials."""
    return await _set_lifecycle(executor_id, db, current_user, "disabled")


@router.post(
    "/{executor_id}/rotate-secret", response_model=LookupExecutorCreateResponse
)
async def rotate_lookup_executor_secret(
    executor_id: UUID, db: DbDep, current_user: MasterUser
) -> LookupExecutorCreateResponse:
    """Generate a pending protocol secret and return it exactly once."""
    del current_user
    executor = await _get_executor(db, executor_id)
    executor, plain_secret = await rotate_secret(db, executor)
    await db.commit()
    await db.refresh(executor)
    return LookupExecutorCreateResponse(executor=executor, plain_secret=plain_secret)


@router.post(
    "/{executor_id}/reveal-hosting-password",
    response_model=HostingPasswordResponse,
)
async def reveal_lookup_executor_hosting_password(
    executor_id: UUID,
    body: MasterPasswordRequest,
    db: DbDep,
    current_user: MasterUser,
) -> HostingPasswordResponse:
    """Reveal an encrypted hosting password after a Master step-up."""
    executor = await _get_executor(db, executor_id)
    try:
        await verify_master_step_up(
            db, current_user, body.password, export_service.get_limiter()
        )
        password = await reveal_hosting_password(executor)
    except MasterStepUpError as exc:
        logger.info(
            "lookup executor hosting password reveal",
            extra={
                "master_id": str(current_user.id),
                "executor_id": str(executor.id),
                "operation": "reveal_hosting_password",
                "outcome": "failure",
            },
        )
        raise _step_up_error(exc) from exc
    except ValueError as exc:
        if str(exc) == "hosting_password_not_configured":
            logger.info(
                "lookup executor hosting password reveal",
                extra={
                    "master_id": str(current_user.id),
                    "executor_id": str(executor.id),
                    "operation": "reveal_hosting_password",
                    "outcome": "not_configured",
                },
            )
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise

    logger.info(
        "lookup executor hosting password reveal",
        extra={
            "master_id": str(current_user.id),
            "executor_id": str(executor.id),
            "operation": "reveal_hosting_password",
            "outcome": "success",
        },
    )
    return HostingPasswordResponse(hosting_account_password=password)


@router.delete("/{executor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lookup_executor(
    executor_id: UUID, db: DbDep, current_user: MasterUser
) -> None:
    """Delete an executor only when jobs and execution leases are idle."""
    del current_user
    executor = await _get_executor(db, executor_id)
    try:
        await delete_executor(db, executor)
    except ExecutorCoordinationUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="executor_coordination_unavailable"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()


__all__ = ["router"]
