"""Read-only deployment check for the existing Neon-backed Phase 1 API."""

import asyncio
from urllib.parse import urlsplit

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import create_database_engine, engine
from app.main import app


async def main() -> None:
    settings = get_settings()
    assert settings.database_url and settings.direct_database_url
    pooled = urlsplit(settings.database_url)
    direct = urlsplit(settings.direct_database_url)
    assert pooled.hostname and pooled.hostname.endswith(".neon.tech")
    assert direct.hostname and direct.hostname.endswith(".neon.tech")
    assert "-pooler" in pooled.hostname and "-pooler" not in direct.hostname
    assert pooled.hostname.replace("-pooler", "") == direct.hostname
    assert pooled.path == direct.path
    assert not settings.allow_test_database_reset and not settings.test_database_url
    direct_engine = create_database_engine(settings.direct_database_url)
    try:
        async with direct_engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "cbdbf24900c6", "Unexpected Phase 1 schema revision"
        print("PASS Neon direct connection and Phase 1 schema; test resets disabled", flush=True)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://deployment-check"
        ) as client:
            for path in ("/health", "/docs", "/openapi.json"):
                assert (await client.get(path)).status_code == 200
                print(f"PASS {path}", flush=True)
            for slug in ("glow-salon-spa", "beatz-dance-studio", "sweet-crumbs"):
                path = f"/api/v1/storefront/{slug}"
                response = await client.get(path)
                assert response.status_code == 200, f"Storefront unavailable: {slug}"
                services = response.json()["services"]
                assert services, f"No offerings: {slug}"
                available = await client.get(
                    f"{path}/available-slots",
                    params={"service_id": services[0]["id"], "date": "2030-01-07"},
                )
                assert available.status_code == 200 and available.json()["available_slots"]
                print(f"PASS Neon storefront and availability: {slug}", flush=True)
    finally:
        await direct_engine.dispose()
        if engine is not None:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
