"""Idempotent owner-only trial notices. No delivery occurs unless explicitly enabled."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import require_aware_utc
from app.models import Merchant
from app.services.email_service import get_last_response_details, send_email

Sender = Callable[..., Awaitable[bool]]
RETRY_DELAY = timedelta(hours=1)
MAX_ATTEMPTS = 5


def reminder_kind(trial_end: datetime, now: datetime) -> str | None:
    remaining = require_aware_utc(trial_end) - require_aware_utc(now)
    if remaining <= timedelta(0):
        return "ended"
    if remaining <= timedelta(days=1):
        return "one_day"
    if remaining <= timedelta(days=3):
        return "three_days"
    return None


def notice(kind: str, business_name: str) -> tuple[str, str]:
    if kind == "three_days":
        return (
            "Your Typein trial ends in 3 days",
            f"{business_name}, your Typein trial ends soon. "
            "Visit the dashboard to review your subscription.",
        )
    if kind == "one_day":
        return (
            "Your Typein trial ends tomorrow",
            f"{business_name}, your Typein trial ends tomorrow. "
            "Visit the dashboard to review your subscription.",
        )
    return (
        "Your Typein trial has ended",
        f"{business_name}, your Typein trial has ended. "
        "Visit the dashboard to review your subscription.",
    )


async def run_trial_reminders(
    db: AsyncSession,
    now: datetime,
    *,
    delivery_enabled: bool = False,
    test_recipient: str | None = None,
    production: bool = False,
    send: Sender = send_email,
) -> dict[str, int]:
    """Process due owners; one provider idempotency key per merchant and notice.

    Staging requires a controlled recipient. Production delivers to the owner.
    The DB row lock serializes workers and is held through the provider call.
    """
    stats = {"due": 0, "sent": 0, "failed": 0, "skipped": 0}
    if not delivery_enabled:
        return stats
    if not production and not test_recipient:
        raise ValueError("A controlled test recipient is required outside production")
    now = require_aware_utc(now)
    candidate_ids = list(await db.scalars(
        select(Merchant.id).where(
            Merchant.trial_ends_at <= now + timedelta(days=3),
            Merchant.subscription_status == "trialing",
            Merchant.subscription_authenticated_at.is_(None),
        ).order_by(Merchant.trial_ends_at, Merchant.id)
    ))
    await db.rollback()
    for merchant_id in candidate_ids:
        async with db.begin():
            merchant = await db.scalar(
                select(Merchant).where(Merchant.id == merchant_id).with_for_update()
            )
            if (
                merchant is None
                or merchant.subscription_status != "trialing"
                or merchant.subscription_authenticated_at is not None
            ):
                stats["skipped"] += 1
                continue
            kind = reminder_kind(merchant.trial_ends_at, now)
            if kind is None:
                stats["skipped"] += 1
                continue
            stats["due"] += 1
            await db.execute(text("""
                INSERT INTO trial_reminder_deliveries (merchant_id, kind, status)
                VALUES (:merchant_id, :kind, 'pending')
                ON CONFLICT (merchant_id, kind) DO NOTHING
            """), {"merchant_id": merchant_id, "kind": kind})
            row = (await db.execute(text("""
                SELECT status, attempt_count, last_attempt_at
                FROM trial_reminder_deliveries
                WHERE merchant_id = :merchant_id AND kind = :kind
                FOR UPDATE
            """), {"merchant_id": merchant_id, "kind": kind})).one()
            if row.status == "sent" or row.attempt_count >= MAX_ATTEMPTS or (
                row.last_attempt_at is not None and
                (
                    require_aware_utc(row.last_attempt_at) > now - RETRY_DELAY
                    or require_aware_utc(row.last_attempt_at) <= now - timedelta(hours=24)
                )
            ):
                stats["skipped"] += 1
                continue
            subject, body = notice(kind, merchant.business_name)
            recipient = merchant.email if production else test_recipient
            environment_key = "live" if production else "test"
            key = f"typein-trial-{environment_key}-{merchant_id}-{kind}"
            success = await send(
                recipient, subject, f"<p>{body}</p>", body, idempotency_key=key
            )
            _, provider_id = get_last_response_details() if send is send_email else (None, None)
            await db.execute(text("""
                UPDATE trial_reminder_deliveries
                SET status = :status, attempt_count = attempt_count + 1,
                    last_attempt_at = :now, sent_at = :sent_at,
                    provider_message_id = :provider_id
                WHERE merchant_id = :merchant_id AND kind = :kind
            """), {
                "status": "sent" if success else "failed",
                "now": now,
                "sent_at": now if success else None,
                "provider_id": provider_id,
                "merchant_id": merchant_id,
                "kind": kind,
            })
            stats["sent" if success else "failed"] += 1
    return stats
