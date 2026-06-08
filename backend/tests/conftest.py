import os
from cryptography.fernet import Fernet

# Set up a valid DATA_ENCRYPTION_KEY for testing before app or config is loaded
os.environ["DATA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_password_hash
from app.main import app
from app.models import Base, Client, MasterProfile, Tenant, User
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
            client_prefix="tna01",
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
            client_prefix="tnb01",
            name="Inactive Tenant",
            whatsapp_phone="+12015550003",
            is_active=False,
        )
    )
    await db_session.commit()
    return user


async def _tenant_for_user(db_session, user_id):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one_or_none()


@pytest_asyncio.fixture
async def active_client_user(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    user = User(
        username=f"{tenant.client_prefix}_client1",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=user.id,
            full_name="Active Client",
            username=f"{tenant.client_prefix}_client1",
            phone="+12015550030",
            is_active=True,
        )
    )
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def inactive_client_user(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    user = User(
        username=f"{tenant.client_prefix}_client2",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=user.id,
            full_name="Inactive Client",
            username=f"{tenant.client_prefix}_client2",
            phone="+12015550031",
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
