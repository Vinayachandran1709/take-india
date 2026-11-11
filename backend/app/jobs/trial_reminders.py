"""Run with python -m app.jobs.trial_reminders from a scheduled Railway job."""

import asyncio
import logging

from app.core.clock import utc_now
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.trial_reminders import run_trial_reminders


async def main() -> None:
    settings = get_settings()
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is required")
    async with SessionLocal() as db:
        stats = await run_trial_reminders(
            db, utc_now(),
            delivery_enabled=settings.trial_reminder_delivery_enabled,
            test_recipient=settings.trial_reminder_test_recipient,
            production=settings.environment == "production",
        )
    logging.info("Trial reminders: %s", stats)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
