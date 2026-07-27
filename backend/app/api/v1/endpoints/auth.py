from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import CurrentUser, MasterUser
from app.schemas.auth import (
    DemoHeartbeatResponse,
    LoginRequest,
    RefreshRequest,
    SwitchTenantRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.services.demo_lifecycle_service import DemoAuthError

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()
DbDep = Annotated[AsyncSession, Depends(get_db)]


def _demo_error(exc: DemoAuthError) -> HTTPException:
    status_code = (
        status.HTTP_410_GONE
        if exc.code == "demo_ended"
        else status.HTTP_401_UNAUTHORIZED
    )
    return HTTPException(status_code=status_code, detail=exc.code)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbDep):
    try:
        user = await auth_service.authenticate(db, payload.username, payload.password)
    except DemoAuthError as exc:
        raise _demo_error(exc) from exc
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or account deactivated",
        )
    try:
        result = await auth_service.create_tokens(db, user)
    except DemoAuthError as exc:
        raise _demo_error(exc) from exc
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or account deactivated",
        )
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: DbDep):
    try:
        result = await auth_service.refresh_access_token(
            db, payload.refresh_token, payload.active_tenant_id
        )
    except DemoAuthError as exc:
        raise _demo_error(exc) from exc
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return result


@router.api_route(
    "/heartbeat",
    methods=["GET", "POST"],
    response_model=DemoHeartbeatResponse,
)
async def heartbeat(db: DbDep, current_user: CurrentUser):
    try:
        return await auth_service.lifecycle_heartbeat(db, current_user)
    except DemoAuthError as exc:
        raise _demo_error(exc) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, db: DbDep):
    try:
        await auth_service.revoke_refresh_token(db, payload.refresh_token)
    except DemoAuthError as exc:
        raise _demo_error(exc) from exc


@router.post("/switch-tenant", response_model=TokenResponse)
async def switch_tenant(
    payload: SwitchTenantRequest, db: DbDep, current_user: MasterUser
):
    result = await auth_service.switch_tenant(db, current_user, payload.tenant_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return result
