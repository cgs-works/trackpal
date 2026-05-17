import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_password_hash
from app.main import app
from app.models import Base, MasterProfile, Tenant, User
from app.services.evolution_client import evolution_client


# Disable Evolution API calls during tests
evolution_client.api_key = ""

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def master_user(db_session):
    user = User(
        username="master",
        password_hash=get_password_hash("master-password"),
        role="master",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def active_tenant_user(db_session):
    user = User(
        username="tenant",
        password_hash=get_password_hash("tenant-password"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Tenant(
            owner_user_id=user.id,
            name="Active Tenant",
            whatsapp_phone="+12015550002",
            is_active=True,
        )
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def deactivated_tenant_user(db_session):
    user = User(
        username="inactive-tenant",
        password_hash=get_password_hash("tenant-password"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Tenant(
            owner_user_id=user.id,
            name="Inactive Tenant",
            whatsapp_phone="+12015550003",
            is_active=False,
        )
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def auth_headers(client, master_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
