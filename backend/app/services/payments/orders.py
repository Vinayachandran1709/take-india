import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import AppError
from app.models import Booking, MerchantPaymentConfig, PaymentTransaction
from app.models.enums import BookingStatus
from app.services.payments.gateway import (
    AmbiguousOrder,
    RazorpayGateway,
    receipt_for,
    validate_amount,
)
from app.services.payments.reconciliation import reconcile_locked
from app.services.payments.security import decrypt, valid_token


async def public_booking(
    db: AsyncSession,
    reference: str,
    token: str,
    *,
    lock: bool = False,
) -> Booking:
    query = select(Booking).where(Booking.booking_reference == reference)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    booking = await db.scalar(query)
    if booking is None or not valid_token(token, booking.public_token_hash):
        raise AppError("NOT_FOUND", "Booking not found", 404)
    return booking


async def lock_attempt(db: AsyncSession, attempt_id: uuid.UUID) -> PaymentTransaction:
    attempt = await db.scalar(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.id == attempt_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if attempt is None:
        raise AppError("NOT_FOUND", "Payment not found", 404)
    return attempt


def require_payable(booking: Booking, now: datetime) -> None:
    if (
        booking.booking_status != BookingStatus.PENDING_PAYMENT
        or booking.hold_expires_at <= now
        or booking.amount_paid > 0
    ):
        raise AppError("BOOKING_NOT_PAYABLE", "The booking hold is no longer payable", 409)


async def payable_order(
    db: AsyncSession,
    reference: str,
    token: str,
    clock: Clock,
    gateway: RazorpayGateway,
) -> dict[str, Any]:
    booking = await public_booking(db, reference, token, lock=True)
    now = clock()
    require_payable(booking, now)
    config = await db.scalar(
        select(MerchantPaymentConfig).where(
            MerchantPaymentConfig.merchant_id == booking.merchant_id,
            MerchantPaymentConfig.is_current.is_(True),
            MerchantPaymentConfig.is_enabled.is_(True),
        )
    )
    if config is None:
        raise AppError("PAYMENTS_UNAVAILABLE", "Merchant payments are disconnected", 409)
    attempt = await db.scalar(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.booking_id == booking.id,
        )
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
        .limit(1)
    )
    create = attempt is None or (attempt.status == "FAILED" and not attempt.provider_order_id)
    if create:
        validate_amount(booking.amount_to_pay)
        attempt_id = uuid.uuid4()
        attempt = PaymentTransaction(
            id=attempt_id,
            merchant_id=booking.merchant_id,
            booking_id=booking.id,
            config_id=config.id,
            receipt=receipt_for(attempt_id),
            amount=booking.amount_to_pay,
            currency="INR",
            status="CREATING",
            created_at=now,
        )
        db.add(attempt)
    else:
        config = await db.get(MerchantPaymentConfig, attempt.config_id)
        if config is None:
            raise AppError("PAYMENT_CONFIGURATION_INVALID", "Payment configuration missing", 503)
        if attempt.status == "CREATING":
            if attempt.created_at + timedelta(seconds=30) > now:
                raise AppError("PAYMENT_PROCESSING", "An order is being created", 409)
            attempt.status = "UNKNOWN"
        if attempt.status == "CAPTURED":
            raise AppError("BOOKING_NOT_PAYABLE", "Payment has already been captured", 409)
    await db.commit()  # Persist intent and release booking lock before network I/O.
    key, secret = config.key_id, decrypt(config.key_secret_encrypted)
    try:
        if create:
            order = await gateway.create_order(key, secret, attempt.amount, "INR", attempt.receipt)
        elif attempt.status == "UNKNOWN":
            order = await gateway.find_order(key, secret, attempt.receipt)
            if order is None:
                raise AmbiguousOrder()
        elif attempt.provider_order_id:
            order = await gateway.fetch_order(key, secret, attempt.provider_order_id)
        else:
            raise AmbiguousOrder()
        try:
            gateway.validate_id(order.get("id", ""), "order_")
        except (AppError, AttributeError, TypeError):
            raise AmbiguousOrder() from None
        if (
            order.get("amount") != validate_amount(attempt.amount)
            or order.get("currency") != "INR"
            or order.get("receipt") != attempt.receipt
        ):
            raise AmbiguousOrder()
    except AppError as exc:
        await public_booking(db, reference, token, lock=True)
        locked = await lock_attempt(db, attempt.id)
        if create and locked.status == "CREATING":
            locked.status = "UNKNOWN" if isinstance(exc, AmbiguousOrder) else "FAILED"
        await db.commit()
        raise
    booking = await public_booking(db, reference, token, lock=True)
    attempt = await lock_attempt(db, attempt.id)
    if attempt.provider_order_id and attempt.provider_order_id != order["id"]:
        raise AppError("PAYMENT_STATE_MISMATCH", "Order identity changed", 409)
    attempt.provider_order_id = order["id"]
    if attempt.status in ("CREATING", "UNKNOWN"):
        attempt.status = "CREATED"
    await db.commit()
    if order.get("status") == "paid":
        payments = await gateway.order_payments(key, secret, order["id"])
        for payment in payments.get("items", []):
            if payment.get("status") == "captured":
                booking = await public_booking(db, reference, token, lock=True)
                attempt = await lock_attempt(db, attempt.id)
                await reconcile_locked(db, booking, attempt, payment, order, clock())
                await db.commit()
                return {"state": "RECONCILED"}
        raise AppError("PAYMENT_PROCESSING", "Paid order is awaiting reconciliation", 409)
    if order.get("status") not in ("created", "attempted"):
        raise AppError("PAYMENT_ORDER_UNKNOWN", "Order state requires investigation", 409)
    booking = await public_booking(db, reference, token, lock=True)
    require_payable(booking, clock())
    await db.commit()
    return {
        "state": "CHECKOUT",
        "key_id": key,
        "order_id": order["id"],
        "amount": validate_amount(attempt.amount),
        "currency": "INR",
    }
