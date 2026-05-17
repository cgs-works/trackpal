from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

RLS_CONTEXT_KEY = "rls_context"
SYSTEM_RLS_USER_ID = "00000000-0000-0000-0000-000000000000"


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def set_rls_context(
    session, user_id: str, role: str, active_tenant_id: str | None
) -> None:
    bind = session.get_bind()
    session.info[RLS_CONTEXT_KEY] = {
        "user_id": user_id,
        "role": role,
        "active_tenant_id": active_tenant_id,
    }
    if bind.dialect.name != "postgresql":
        return
    if role != "master" and not active_tenant_id:
        raise ValueError("active_tenant_id required for tenant RLS context")
    await session.execute(
        text(
            "SELECT set_config('app.current_user_id', :user_id, true), "
            "set_config('app.current_role', :role, true), "
            "set_config('app.active_tenant_id', :tenant_id, true)"
        ),
        {"user_id": user_id, "role": role, "tenant_id": active_tenant_id or ""},
    )


async def restore_rls_context(session) -> None:
    context = get_rls_context(session)
    if context is None:
        return
    await set_rls_context(
        session,
        context["user_id"],
        context["role"],
        context["active_tenant_id"],
    )


def get_rls_context(session) -> dict[str, str | None] | None:
    return session.info.get(RLS_CONTEXT_KEY)


async def set_internal_rls_context(session) -> None:
    """Set safe internal RLS context for API-key/auth flows.

    These flows run before JWT dependencies can establish user context but still
    need to query FORCE-RLS tables such as tenants. Use master role with a fixed
    non-user id and no active tenant so tenant-management reads are allowed while
    tenant-scoped catalog policies still require explicit active_tenant_id.
    """
    await set_rls_context(session, SYSTEM_RLS_USER_ID, "master", None)
