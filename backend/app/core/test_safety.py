from sqlalchemy.engine import make_url

from app.core.config import Settings


def database_identity(value: str) -> tuple[str, int, str]:
    """Treat Neon pooled/direct URLs as the same database, regardless of credentials."""
    url = make_url(value)
    host = (url.host or "").lower().replace("-pooler.", ".")
    if not host or not url.database:
        raise ValueError("Database URL must identify a host and database")
    return host, url.port or 5432, url.database


def assert_test_database_safe(settings: Settings) -> str:
    failures: list[str] = []
    if settings.environment != "test":
        failures.append("ENVIRONMENT must be exactly 'test'")
    if not settings.test_database_url:
        failures.append("TEST_DATABASE_URL must be configured")
    if settings.test_database_url and settings.test_database_url == settings.database_url:
        failures.append("TEST_DATABASE_URL must differ from DATABASE_URL")
    if settings.test_database_url:
        try:
            target = database_identity(settings.test_database_url)
            for name in ("database_url", "direct_database_url"):
                other = getattr(settings, name)
                if other and database_identity(other) == target:
                    failures.append(f"TEST_DATABASE_URL must differ from {name.upper()}")
        except Exception:
            failures.append("Database identities could not be safely verified")
    if not settings.allow_test_database_reset:
        failures.append("ALLOW_TEST_DATABASE_RESET must be true")
    if failures:
        raise RuntimeError("Unsafe test database configuration: " + "; ".join(failures))
    return settings.test_database_url
