"""Verified, deduplicated Razorpay subscription webhooks."""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import BillingPayment, BillingWebhookEvent, Merchant
from app.services.billing_service import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["billing webhooks"])
logger = logging.getLogger(__name__)

EVENT_STATUS = {
    "subscription.authenticated": "trialing",
    "subscription.activated": "active",
    "subscription.charged": "active",
    "subscription.pending": "past_due",
    "subscription.halted": "past_due",
    "subscription.paused": "past_due",
    "subscription.resumed": "active",
    "subscription.cancelled": "cancelled",
    "subscription.completed": "expired",
}
EVENT_RANK = {
    "subscription.authenticated": 1,
    "subscription.activated": 2,
    "subscription.resumed": 2,
    "subscription.charged": 4,
    "subscription.pending": 3,
    "subscription.paused": 3,
    "subscription.halted": 5,
    "subscription.cancelled": 6,
    "subscription.completed": 6,
}


def is_stale_event(
    event_time: datetime, event_type: str, previous: tuple[datetime, str] | None
) -> bool:
    return bool(previous and (
        event_time < previous[0]
        or (event_time == previous[0] and EVENT_RANK[event_type] <= EVENT_RANK.get(previous[1], 0))
    ))


def valid_charge(payment: dict[str, Any], amount_paise: int) -> bool:
    payment_id = payment.get("id")
    return (
        isinstance(payment_id, str) and payment_id.startswith("pay_")
        and payment.get("amount") == amount_paise
        and payment.get("currency") == "INR"
        and payment.get("status") == "captured"
    )


def _entity(data: dict[str, Any], kind: str) -> dict[str, Any] | None:
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return None
    wrapper = payload.get(kind)
    if not isinstance(wrapper, dict):
        return None
    value = wrapper.get("entity")
    return value if isinstance(value, dict) else None


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        try:
            return datetime.fromtimestamp(value, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


async def _record_charge(
    db: DatabaseSession, merchant: Merchant, subscription_id: str,
    payment: dict[str, Any], amount_paise: int,
) -> bool:
    if not valid_charge(payment, amount_paise):
        return False
    payment_id = payment["id"]
    await db.execute(
        insert(BillingPayment).values(
            id=uuid.uuid4(), merchant_id=merchant.id,
            razorpay_payment_id=payment_id, razorpay_subscription_id=subscription_id,
            amount_paise=amount_paise, currency="INR", status="captured",
            paid_at=_timestamp(payment.get("created_at")),
        ).on_conflict_do_nothing(constraint="uq_billing_payments_razorpay_payment_id")
    )
    return True


async def process_verified_event(db: DatabaseSession, event_id: str, body: bytes,
                                 data: dict[str, Any]) -> str:
    """Persist the event id before applying any transition; return a safe result label."""
    now = datetime.now(UTC)
    event_type = data.get("event")
    event_time = _timestamp(data.get("created_at"))
    subscription = _entity(data, "subscription")
    subscription_id = subscription.get("id") if subscription else None
    inserted = await db.execute(
        insert(BillingWebhookEvent).values(
            event_id=event_id, event_type=event_type, subscription_id=subscription_id,
            payload_hash=hashlib.sha256(body).hexdigest(), processing_status="received",
            event_created_at=event_time,
        ).on_conflict_do_nothing(index_elements=["event_id"]).returning(BillingWebhookEvent.event_id)
    )
    if inserted.scalar_one_or_none() is None:
        return "duplicate"

    record = await db.get(BillingWebhookEvent, event_id)

    def finish(status: str, code: str | None = None) -> str:
        record.processing_status = status
        record.error_code = code
        record.processed_at = now
        return status

    if event_type not in EVENT_STATUS or not isinstance(subscription_id, str):
        return finish("ignored", "unknown_event")
    if event_time is None:
        return finish("ignored", "missing_event_time")
    merchant = await db.scalar(
        select(Merchant).where(Merchant.razorpay_subscription_id == subscription_id)
        .with_for_update()
    )
    if merchant is None:
        logger.warning("Razorpay billing webhook for an unknown subscription")
        return finish("ignored", "unknown_subscription")
    settings = get_settings()
    if (
        subscription.get("plan_id") != settings.razorpay_plan_id
        or subscription.get("quantity") != 1
    ):
        logger.warning("Razorpay billing webhook plan anomaly")
        return finish("ignored", "plan_mismatch")

    if event_type == "subscription.charged":
        payment = _entity(data, "payment")
        if not payment or not await _record_charge(
            db, merchant, subscription_id, payment, settings.billing_plan_amount_paise
        ):
            logger.warning("Razorpay billing webhook amount or payment anomaly")
            return finish("ignored", "amount_mismatch")

    period_end = _timestamp(subscription.get("current_end"))
    if event_type in (
        "subscription.activated", "subscription.charged", "subscription.resumed"
    ) and period_end is None:
        logger.warning("Razorpay billing webhook missing billing period")
        return finish("ignored", "period_missing")

    previous = (await db.execute(
        select(BillingWebhookEvent.event_created_at, BillingWebhookEvent.event_type)
        .where(BillingWebhookEvent.subscription_id == subscription_id,
               BillingWebhookEvent.processing_status == "applied")
        .order_by(BillingWebhookEvent.event_created_at.desc(),
                  BillingWebhookEvent.processed_at.desc()).limit(1)
    )).first()
    if is_stale_event(event_time, event_type, previous):
        return finish("ignored", "stale_event")

    if event_type == "subscription.authenticated":
        merchant.subscription_authenticated_at = event_time
        merchant.checkout_confirmed_at = None
        # Authentication of a future-dated subscription is not a paid cycle.
    else:
        merchant.subscription_status = EVENT_STATUS[event_type]
        if event_type in ("subscription.activated", "subscription.charged", "subscription.resumed"):
            merchant.subscription_authenticated_at = event_time
            merchant.checkout_confirmed_at = None
    if period_end is not None:
        merchant.current_period_end = period_end
    if event_type in ("subscription.cancelled", "subscription.completed"):
        merchant.cancel_at_period_end = False
    return finish("applied")


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request, db: DatabaseSession, response: Response
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    if settings.razorpay_webhook_secret is None:
        raise AppError("BILLING_UNAVAILABLE", "Billing webhook is not configured", 503)
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > 256_000:
            raise AppError("INVALID_WEBHOOK", "Webhook body is too large", 413)
        chunks.extend(chunk)
    body = bytes(chunks)
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_webhook_signature(
        settings.razorpay_webhook_secret.get_secret_value(), body, signature
    ):
        raise AppError("INVALID_WEBHOOK", "Webhook signature is invalid", 400)
    event_id = request.headers.get("x-razorpay-event-id", "")
    if not event_id or len(event_id) > 120:
        raise AppError("INVALID_WEBHOOK", "Webhook event id is missing", 400)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("INVALID_WEBHOOK", "Webhook body is invalid", 400) from exc
    if not isinstance(data, dict) or not isinstance(data.get("event"), str):
        raise AppError("INVALID_WEBHOOK", "Webhook body is invalid", 400)
    try:
        result = await process_verified_event(db, event_id, body, data)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("Razorpay billing webhook database failure: %s", type(exc).__name__)
        raise AppError("BILLING_UNAVAILABLE", "Webhook could not be processed", 503) from exc
    return {"status": result}
