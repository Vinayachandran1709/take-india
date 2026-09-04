from app.core.config import Settings


def assert_test_database_safe(settings: Settings) -> str:
    failures: list[str] = []
    if settings.environment != "test":
        failures.append("ENVIRONMENT must be exactly 'test'")
    if not settings.test_database_url:
        failures.append("TEST_DATABASE_URL must be configured")
    if settings.database_url and settings.test_database_url == settings.database_url:
        failures.append("TEST_DATABASE_URL must differ from DATABASE_URL")
    if not settings.allow_test_database_reset:
        failures.append("ALLOW_TEST_DATABASE_RESET must be true")
    if failures:
        raise RuntimeError("Unsafe test database configuration: " + "; ".join(failures))
    return settings.test_database_url

