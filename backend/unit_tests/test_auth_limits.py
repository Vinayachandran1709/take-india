import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_limits import AuthRateLimiter
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.slugs import is_reserved_slug
from app.v1_main import app


def test_reserved_storefront_names() -> None:
    assert is_reserved_slug("api")
    assert is_reserved_slug("typein")
    assert not is_reserved_slug("my-salon")


async def test_auth_budget_reopens_at_exact_boundary() -> None:
    limiter = AuthRateLimiter()
    await limiter.check("login:client", max_requests=2, window_seconds=60, now=100)
    await limiter.check("login:client", max_requests=2, window_seconds=60, now=101)
    with pytest.raises(AppError) as raised:
        await limiter.check("login:client", max_requests=2, window_seconds=60, now=159)
    assert raised.value.status_code == 429
    await limiter.check("login:client", max_requests=2, window_seconds=60, now=160)


async def test_auth_budgets_are_isolated() -> None:
    limiter = AuthRateLimiter()
    await limiter.check("signup:client", max_requests=1, window_seconds=3600, now=1)
    await limiter.check("login:client", max_requests=1, window_seconds=600, now=1)
    with pytest.raises(AppError):
        await limiter.check("signup:client", max_requests=1, window_seconds=3600, now=2)


async def test_reserved_slug_endpoint_never_queries_database() -> None:
    class FakeSession:
        async def scalar(self, _statement):
            raise AssertionError("Reserved names must not query the database")

    async def fake_db():
        yield FakeSession()

    app.dependency_overrides[get_db] = fake_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/slug-available", params={"slug": "api"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"available": False}
