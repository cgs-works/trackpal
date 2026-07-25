from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, set_internal_rls_context, set_rls_context
from app.core.demo_guardrail import (
    DemoGuardrailError,
    assert_demo_operation_allowed,
)
from app.core.security import decode_token, verify_n8n_api_key
from app.core.tenant_plan import TENANT_PLAN_PRO, TenantPlan
from app.repositories import (
    clients_repository,
    tenants_repository,
    tenant_settings_repository,
    users_repository,
)
from app.models import User
from app.services.demo_lifecycle_service import DemoAuthError, ensure_demo_request



async def resolve_locale(db: AsyncSession, tenant_id: UUID) -> str:
    return await tenant_settings_repository.resolve_locale(db, tenant_id)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        parsed_user_id = UUID(user_id)
    except (ValueError, TypeError):
        raise credentials_exception from None

    user = await users_repository.get(db, parsed_user_id)
    if user is None:
        raise credentials_exception
    try:
        await set_rls_context(
            db, str(user.id), user.role, payload.get("active_tenant_id")
        )
    except ValueError:
        raise credentials_exception from None
    if user.role == "tenant":
        profile = await tenants_repository.get_by_owner(db, user.id)
        if profile and not profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
            )
        raw_demo_version = payload.get("demo_credentials_version")
        try:
            demo_version = (
                int(raw_demo_version) if raw_demo_version is not None else None
            )
        except (TypeError, ValueError):
            raise credentials_exception from None
        try:
            await ensure_demo_request(db, user, credential_version=demo_version)
        except DemoAuthError as exc:
            code_status = (
                status.HTTP_410_GONE
                if exc.code == "demo_ended"
                else status.HTTP_401_UNAUTHORIZED
            )
            raise HTTPException(status_code=code_status, detail=exc.code) from exc
    if user.role == "client":
        raw_tenant_id = payload.get("active_tenant_id")
        if not raw_tenant_id:
            raise credentials_exception
        try:
            tenant_id = UUID(raw_tenant_id)
        except (ValueError, TypeError):
            raise credentials_exception from None
        if (
            await clients_repository.get_active_client_in_tenant(db, user.id, tenant_id)
            is None
        ):
            raise credentials_exception
    return user


async def require_demo_guardrail(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Allow only production identities to use production-only endpoints."""
    if current_user.role != "tenant":
        return current_user

    tenant = await tenants_repository.get_by_owner(db, current_user.id)
    if tenant is None:
        return current_user
    try:
        assert_demo_operation_allowed(tenant, operation="authenticated_endpoint")
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.code,
        ) from exc
    return current_user




async def get_active_tenant_id(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_demo_guardrail)],
) -> UUID:
    payload = decode_token(token)
    if current_user.role == "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients cannot access tenant management endpoints",
        )
    if current_user.role == "tenant":
        tenant = await tenants_repository.get_active_by_owner(db, current_user.id)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
            )
        await set_rls_context(
            db, str(current_user.id), current_user.role, str(tenant.id)
        )
        return tenant.id
    raw = payload.get("active_tenant_id")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active tenant context required",
        )
    try:
        tenant_id = UUID(raw)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant context"
        ) from None
    tenant = await tenants_repository.get_active(db, tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active tenant context required",
        )
    try:
        assert_demo_operation_allowed(tenant, operation="tenant_scoped")
    except DemoGuardrailError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.code,
        ) from exc
    await set_rls_context(db, str(current_user.id), current_user.role, str(tenant_id))
    return tenant_id


async def get_current_tenant_plan(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_demo_guardrail)],
) -> TenantPlan | None:
    payload = decode_token(token)
    if current_user.role == "tenant":
        tenant = await tenants_repository.get_active_by_owner(db, current_user.id)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
            )
        return tenant.plan  # type: ignore[return-value]
    if current_user.role == "master":
        raw = payload.get("active_tenant_id")
        if not raw:
            return None
        try:
            tenant_id = UUID(raw)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid tenant context",
            ) from None
        tenant = await tenants_repository.get_active(db, tenant_id)
        if tenant is not None:
            try:
                assert_demo_operation_allowed(tenant, operation="tenant_settings")
            except DemoGuardrailError as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=exc.code,
                ) from exc
        return tenant.plan if tenant else None  # type: ignore[return-value]
    return None


async def get_pro_tenant_id(
    tenant_id: Annotated[UUID, Depends(get_active_tenant_id)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UUID:
    if current_user.role == "master":
        return tenant_id
    tenant = await tenants_repository.get_active(db, tenant_id)
    if tenant is None or tenant.plan != TENANT_PLAN_PRO:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return tenant_id


def require_role(required_role: str):
    async def role_checker(current_user: Annotated[User, Depends(get_current_user)]):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user

    return role_checker


async def verify_n8n_api_key_header(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
):
    """Verify n8n API key from header."""
    if not x_api_key or not verify_n8n_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return True


async def set_api_key_rls_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    verified: Annotated[bool, Depends(verify_n8n_api_key_header)],
) -> AsyncSession:
    await set_internal_rls_context(db)
    return db


CurrentUser = Annotated[User, Depends(get_current_user)]
DemoGuardedUser = Annotated[User, Depends(require_demo_guardrail)]
MasterUser = Annotated[User, Depends(require_role("master"))]
DbDep = Annotated[AsyncSession, Depends(get_db)]
ApiKeyDbDep = Annotated[AsyncSession, Depends(set_api_key_rls_context)]
ActiveTenantId = Annotated[UUID, Depends(get_active_tenant_id)]
TenantPlanDep = Annotated[TenantPlan | None, Depends(get_current_tenant_plan)]
ProTenantId = Annotated[UUID, Depends(get_pro_tenant_id)]
