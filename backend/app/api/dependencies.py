from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, verify_n8n_api_key
from app.crud import users as user_crud
from app.models import TenantProfile, User
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
    if user.role == "tenant":
        result = await db.execute(
            select(TenantProfile).where(TenantProfile.id == user.id)
        )
        profile = result.scalar_one_or_none()
        if profile and not profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
            )
    return user


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


CurrentUser = Annotated[User, Depends(get_current_user)]
MasterUser = Annotated[User, Depends(require_role("master"))]
DbDep = Annotated[AsyncSession, Depends(get_db)]
