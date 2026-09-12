import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import AppError
from app.models import Booking, MerchantPaymentConfig, PaymentTransaction, PaymentWebhookEvent
from app.services.payments.gateway import RazorpayGateway
from app.services.payments.orders import lock_attempt
from app.services.payments.reconciliation import reconcile_locked
from app.services.payments.security import decrypt, verify_signature

SAFE_FAILURE_VALUES = frozenset(
    {
        "BAD_REQUEST_ERROR",
        "GATEWAY_ERROR",
        "SERVER_ERROR",
        "UNAUTHORIZED_ERROR",
        "payment_failed",
        "payment_cancelled",
        "payment_timed_out",
        "bank_declined",
        "insufficient_funds",
        "authentication_failed",
        "input_validation_failed",
        "card_expired",
        "card_number_invalid",
        "payment_method_not_enabled",
        "issuer_declined",
        "bank_not_available",
        "payment_risk_check_failed",
    }
)


def safe_failure(value: Any) -> str | None:
    # An explicit allowlist prevents even a provider's unexpected machine-code
    # field from persisting arbitrary customer text. Unknown values are omitted.
    return value if isinstance(value, str) and value in SAFE_FAILURE_VALUES else None


def payment_entity(event: dict[str, Any]) -> dict[str, Any]:
    value: Any = event
    for field in ("payload", "payment", "entity"):
        value = value.get(field) if isinstance(value, dict) else None
    return value if isinstance(value, dict) else {}


def dedupe_key(config_id: UUID, event_id: str | None, event: dict[str, Any]) -> str:
    if event_id is not None:
        identity = [str(config_id), "event-id", event_id]
    else:
        payment = payment_entity(event)
        identity = [
            str(config_id),
            "fallback",
            event.get("event"),
            payment.get("order_id"),
            payment.get("id"),
        ]
        if not payment.get("id"):
            identity.append(
                hashlib.sha256(
                    json.dumps(
                        event,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
            )
    return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()


async def process_webhook(
    db: AsyncSession,
    opaque_id: UUID,
    raw: bytes,
    signature: str,
    event_id: str | None,
    clock: Clock,
    gateway: RazorpayGateway,
) -> None:
    config = await db.scalar(
        select(MerchantPaymentConfig).where(
            MerchantPaymentConfig.webhook_id == opaque_id,
        )
    )
    if config is None:
        raise AppError("NOT_FOUND", "Webhook configuration not found", 404)
    verify_signature(
        raw, signature, decrypt(config.webhook_secret_encrypted), "WEBHOOK_SIGNATURE_INVALID"
    )
    try:
        event = json.loads(raw)
        event_type = event["event"]
        if not isinstance(event_type, str) or len(event_type) > 100:
            raise ValueError
        payment = payment_entity(event)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise AppError("WEBHOOK_PAYLOAD_INVALID", "Invalid signed event", 400) from None
    if event_id is not None and (not event_id or len(event_id) > 200):
        raise AppError("WEBHOOK_EVENT_ID_INVALID", "Invalid event identifier", 400)
    dedupe = dedupe_key(config.id, event_id, event)
    if await db.scalar(
        select(PaymentWebhookEvent.id).where(
            PaymentWebhookEvent.dedupe_key == dedupe,
        )
    ):
        return
    relevant = event_type in ("payment.captured", "payment.failed")
    attempt = None
    order = None
    if relevant:
        gateway.validate_id(payment.get("id", ""), "pay_")
        gateway.validate_id(payment.get("order_id", ""), "order_")
        attempt = await db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.config_id == config.id,
                PaymentTransaction.merchant_id == config.merchant_id,
                PaymentTransaction.provider_order_id == payment["order_id"],
            )
        )
        if attempt is None:
            # Order response may still be in flight. Retry rather than losing capture.
            raise AppError(
                "PAYMENT_RECONCILIATION_PENDING", "Payment attempt not yet available", 503
            )
        if event_type == "payment.captured":
            order = await gateway.fetch_order(
                config.key_id, decrypt(config.key_secret_encrypted), payment["order_id"]
            )
            if order.get("status") != "paid":
                raise AppError(
                    "PAYMENT_RECONCILIATION_PENDING",
                    "Captured order state is not yet ready",
                    503,
                )
    await db.commit()  # No network requests after acquiring business/resource locks.
    if attempt:
        booking = await db.scalar(
            select(Booking)
            .where(
                Booking.id == attempt.booking_id,
                Booking.merchant_id == config.merchant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        attempt = await lock_attempt(db, attempt.id)
    inserted = await db.scalar(
        insert(PaymentWebhookEvent)
        .values(
            config_id=config.id,
            provider="RAZORPAY",
            provider_event_id=event_id,
            event_type=event_type,
            dedupe_key=dedupe,
            payload_hash=hashlib.sha256(raw).hexdigest(),
            provider_order_id=payment.get("order_id") if relevant else None,
            provider_payment_id=payment.get("id") if relevant else None,
            processing_status="PROCESSED" if relevant else "IGNORED",
            processed_at=clock(),
        )
        .on_conflict_do_nothing(index_elements=[PaymentWebhookEvent.dedupe_key])
        .returning(PaymentWebhookEvent.id)
    )
    if inserted is None:
        await db.commit()
        return
    if attempt and event_type == "payment.failed":
        if attempt.status != "CAPTURED":
            attempt.status = "FAILED"
            attempt.failure_code = safe_failure(payment.get("error_code"))
            attempt.failure_reason = safe_failure(payment.get("error_reason"))
    elif attempt and order:
        try:
            await reconcile_locked(db, booking, attempt, payment, order, clock())
        except AppError as exc:
            if exc.code != "PAYMENT_STATE_MISMATCH":
                raise
            record = await db.get(PaymentWebhookEvent, inserted)
            record.processing_status = "REJECTED"
            record.error_code = exc.code
    await db.commit()
