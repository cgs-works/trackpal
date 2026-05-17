from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, set_internal_rls_context, set_rls_context
from app.core.security import decode_token, verify_n8n_api_key
from app.crud import users as user_crud
from app.models import Tenant, User
from sqlalchemy import select

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

    user = await user_crud.get(db, parsed_user_id)
    if user is None:
        raise credentials_exception
    await set_rls_context(db, str(user.id), user.role, payload.get("active_tenant_id"))
    if user.role == "tenant":
        result = await db.execute(select(Tenant).where(Tenant.owner_user_id == user.id))
        profile = result.scalar_one_or_none()
        if profile and not profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
            )
    return user


async def get_active_tenant_id(
    token: Annotated[str, Depends(oauth2_scheme)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UUID:
    payload = decode_token(token)
    if current_user.role == "tenant":
        result = await db.execute(select(Tenant).where(Tenant.owner_user_id == current_user.id, Tenant.is_active))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is deactivated")
        await set_rls_context(db, str(current_user.id), current_user.role, str(tenant.id))
        return tenant.id
    raw = payload.get("active_tenant_id")
    if not raw:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active tenant context required")
    try:
        tenant_id = UUID(raw)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant context") from None
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active tenant context required")
    await set_rls_context(db, str(current_user.id), current_user.role, str(tenant_id))
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
MasterUser = Annotated[User, Depends(require_role("master"))]
DbDep = Annotated[AsyncSession, Depends(get_db)]
ApiKeyDbDep = Annotated[AsyncSession, Depends(set_api_key_rls_context)]
ActiveTenantId = Annotated[UUID, Depends(get_active_tenant_id)]
