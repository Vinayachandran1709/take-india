from datetime import UTC, datetime, timedelta

import pytest

from app.services.trial_reminders import notice, reminder_kind, run_trial_reminders

NOW = datetime(2030, 1, 10, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(days=3, seconds=1), None),
        (timedelta(days=3), "three_days"),
        (timedelta(days=1, seconds=1), "three_days"),
        (timedelta(days=1), "one_day"),
        (timedelta(seconds=1), "one_day"),
        (timedelta(0), "ended"),
        (-timedelta(seconds=1), "ended"),
    ],
)
def test_reminder_windows_at_exact_boundaries(offset, expected):
    assert reminder_kind(NOW + offset, NOW) == expected


async def test_delivery_is_off_by_default_and_does_not_touch_database():
    class NoDatabase:
        def __getattr__(self, name):
            raise AssertionError(f"Database unexpectedly accessed: {name}")

    assert await run_trial_reminders(NoDatabase(), NOW) == {
        "due": 0, "sent": 0, "failed": 0, "skipped": 0,
    }


async def test_staging_delivery_requires_a_controlled_inbox():
    with pytest.raises(ValueError, match="controlled test recipient"):
        await run_trial_reminders(object(), NOW, delivery_enabled=True)


def test_notices_contain_no_customer_information():
    for kind in ("three_days", "one_day", "ended"):
        subject, body = notice(kind, "Sample Business")
        assert "Typein trial" in subject
        assert "Sample Business" in body
