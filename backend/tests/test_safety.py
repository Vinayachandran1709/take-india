import pytest

from app.core.config import Settings
from app.core.test_safety import assert_test_database_safe


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"environment": "development"}, "ENVIRONMENT"),
        ({"test_database_url": None}, "TEST_DATABASE_URL"),
        ({"test_database_url": "postgresql://same"}, "must differ"),
        ({"allow_test_database_reset": False}, "ALLOW_TEST_DATABASE_RESET"),
    ],
)
def test_destructive_test_setup_requires_every_guard(
    values: dict[str, object], expected: str
) -> None:
    base: dict[str, object] = {
        "environment": "test",
        "database_url": "postgresql://same",
        "test_database_url": "postgresql://isolated",
        "allow_test_database_reset": True,
    }
    with pytest.raises(RuntimeError, match=expected):
        assert_test_database_safe(Settings(**(base | values)))
