from fastapi import HTTPException, status

from app.api.dependencies import CurrentUser


def require_tenant_or_master(current_user: CurrentUser) -> None:
    """Check current user has tenant or master role."""
    if current_user.role not in ("tenant", "master"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role 'tenant' or 'master' required",
        )
