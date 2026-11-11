from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient

import app.v1_main as v1_main


class WorkingEngine:
    @asynccontextmanager
    async def connect(self):
        yield self

    async def execute(self, _statement):
        return None


class BrokenEngine:
    @asynccontextmanager
    async def connect(self):
        raise OSError("private database detail")
        yield  # pragma: no cover


async def test_readiness_checks_database(monkeypatch):
    monkeypatch.setattr(v1_main, "engine", WorkingEngine())
    async with AsyncClient(
        transport=ASGITransport(app=v1_main.app), base_url="http://test"
    ) as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_fails_closed_without_database_detail(monkeypatch):
    monkeypatch.setattr(v1_main, "engine", BrokenEngine())
    async with AsyncClient(
        transport=ASGITransport(app=v1_main.app), base_url="http://test"
    ) as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "private database detail" not in response.text
