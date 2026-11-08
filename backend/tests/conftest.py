from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies import get_clock
from app.core.config import get_settings
from app.core.database import create_database_engine, get_db
from app.core.test_safety import assert_test_database_safe
from app.phase2_main import app

FIXED_NOW = datetime(2030, 1, 6, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    test_url = assert_test_database_safe(settings)
    engine = create_database_engine(test_url)
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_database(test_engine: AsyncEngine) -> AsyncIterator[None]:
    # This destructive operation is reachable only after assert_test_database_safe passes.
    async with test_engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE TABLE bookings, service_staff, service_custom_fields, "
                "batch_schedules, operating_hours, customers, staff_members, services, "
                "merchants CASCADE"
            )
        )
    yield


@pytest_asyncio.fixture
async def session_maker(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def db(session_maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_clock] = lambda: (lambda: FIXED_NOW)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as api_client:
        yield api_client
    app.dependency_overrides.clear()
