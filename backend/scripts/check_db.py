import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import create_database_engine


async def check(label: str, url: str | None) -> None:
    if not url:
        raise RuntimeError(f"{label} is not configured")
    engine = create_database_engine(url)
    try:
        async with engine.connect() as connection:
            value = await connection.scalar(text("SELECT 1"))
        if value != 1:
            raise RuntimeError(f"{label} returned an unexpected result")
        print(f"{label}: connected")
    finally:
        await engine.dispose()


async def main() -> None:
    settings = get_settings()
    await check("DATABASE_URL", settings.database_url)
    await check("DIRECT_DATABASE_URL", settings.direct_database_url)
    await check("TEST_DATABASE_URL", settings.test_database_url)


if __name__ == "__main__":
    asyncio.run(main())

