import ssl
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def normalize_database_url(raw_url: str) -> tuple[str, dict[str, object]]:
    """Normalize a Neon URL for SQLAlchemy asyncpg without weakening TLS."""
    parsed = urlsplit(raw_url.strip())
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError("Database URL must use PostgreSQL")

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    ssl_mode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    normalized = urlunsplit(
        ("postgresql+asyncpg", parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )

    connect_args: dict[str, object] = {}
    if ssl_mode and ssl_mode.lower() not in {"disable", "allow"}:
        connect_args["ssl"] = ssl.create_default_context()
    return normalized, connect_args


def create_database_engine(raw_url: str, *, echo: bool = False) -> AsyncEngine:
    url, connect_args = normalize_database_url(raw_url)
    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


settings = get_settings()
engine = create_database_engine(settings.database_url) if settings.database_url else None
SessionLocal = (
    async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession) if engine else None
)


async def get_db() -> AsyncIterator[AsyncSession]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionLocal() as session:
        yield session

