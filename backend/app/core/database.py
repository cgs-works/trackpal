from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def set_rls_context(
    session, user_id: str, role: str, active_tenant_id: str | None
) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    await session.execute(
        text(
            "SELECT set_config('app.current_user_id', :user_id, true), "
            "set_config('app.current_role', :role, true), "
            "set_config('app.active_tenant_id', :tenant_id, true)"
        ),
        {"user_id": user_id, "role": role, "tenant_id": active_tenant_id or ""},
    )
