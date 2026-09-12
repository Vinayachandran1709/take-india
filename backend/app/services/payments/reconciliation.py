"""Financial reconciliation; caller owns the transaction and performs network I/O first."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models import (
    BatchSchedule,
    Booking,
    Customer,
    Merchant,
    PaymentTransaction,
    Service,
    StaffMember,
)
from app.models.enums import BookingMode, BookingStatus, PaymentStatus
from app.models.payments import PaymentCaptureAnomaly
from app.services.availability_service import occupying_booking
from app.services.booking_service import has_overlap
from app.services.payments.security import to_paise


async def resource_available(db: AsyncSession, booking: Booking, now: datetime) -> bool:
    service = await db.get(Service, booking.service_id)
    if service is None or service.merchant_id != booking.merchant_id:
        return False
    if service.booking_mode == BookingMode.APPOINTMENT:
        if booking.staff_member_id:
            resource = await db.scalar(
                select(StaffMember)
                .where(
                    StaffMember.id == booking.staff_member_id,
                    StaffMember.merchant_id == booking.merchant_id,
                )
                .with_for_update()
            )
        else:
            resource = await db.scalar(
                select(Merchant)
                .where(
                    Merchant.id == booking.merchant_id,
                )
                .with_for_update()
            )
        if resource is None:
            return False
        return not await has_overlap(
            db,
            merchant_id=booking.merchant_id,
            booking_date=booking.booking_date,
            start_time=booking.start_time,
            end_time=booking.end_time,
            now_utc=now,
            staff_member_id=booking.staff_member_id,
            exclude_booking_id=booking.id,
        )
    if service.booking_mode == BookingMode.BATCH:
        batch = await db.scalar(
            select(BatchSchedule)
            .where(
                BatchSchedule.id == booking.batch_schedule_id,
                BatchSchedule.merchant_id == booking.merchant_id,
            )
            .with_for_update()
        )
        if batch is None:
            return False
        count = await db.scalar(
            select(func.count(Booking.id)).where(
                Booking.merchant_id == booking.merchant_id,
                Booking.batch_schedule_id == batch.id,
                Booking.booking_date == booking.booking_date,
                Booking.id != booking.id,
                occupying_booking(now),
            )
        )
        return int(count or 0) < batch.max_capacity
    # Custom orders have no exclusive resource/capacity in Phase 1. Lead time was
    # validated at initiation and must not be reapplied to a captured payment.
    return True


def validate_capture(
    booking: Booking,
    attempt: PaymentTransaction,
    payment: dict[str, Any],
    order: dict[str, Any],
) -> None:
    expected = to_paise(attempt.amount)
    if not (
        attempt.booking_id == booking.id
        and attempt.merchant_id == booking.merchant_id
        and attempt.amount == booking.amount_to_pay
        and payment.get("id")
        and payment.get("status") == "captured"
        and payment.get("captured") is True
        and payment.get("order_id") == attempt.provider_order_id == order.get("id")
        and payment.get("currency") == order.get("currency") == attempt.currency == "INR"
        and type(payment.get("amount")) is int
        and payment["amount"] == expected
        and type(order.get("amount")) is int
        and order["amount"] == expected
        and order.get("status") == "paid"
        and order.get("amount_paid") == expected
    ):
        raise AppError("PAYMENT_STATE_MISMATCH", "Provider payment does not match the booking", 409)


async def reconcile_locked(
    db: AsyncSession,
    booking: Booking,
    attempt: PaymentTransaction,
    payment: dict[str, Any],
    order: dict[str, Any],
    now: datetime,
) -> None:
    """Booking then attempt must already be locked, in that order."""
    validate_capture(booking, attempt, payment, order)
    payment_id = payment["id"]
    if attempt.status == "CAPTURED":
        if attempt.provider_payment_id != payment_id:
            await record_anomaly(db, attempt, payment_id)
            attempt.reconciliation_state = "DUPLICATE_CAPTURE_REVIEW"
        return
    attempt.status = "CAPTURED"
    attempt.provider_payment_id = payment_id
    attempt.captured_at = now
    attempt.failure_code = None
    attempt.failure_reason = None
    if booking.amount_paid > 0:
        await record_anomaly(db, attempt, payment_id)
        attempt.reconciliation_state = "DUPLICATE_CAPTURE_REVIEW"
        return
    booking.amount_paid = attempt.amount
    booking.payment_status = (
        PaymentStatus.FULLY_PAID if booking.balance_due == 0 else PaymentStatus.ADVANCE_PAID
    )
    # Compatibility only; payment_transactions is the authoritative provider record.
    booking.razorpay_order_id = attempt.provider_order_id
    booking.razorpay_payment_id = payment_id
    eligible = booking.booking_status in (BookingStatus.PENDING_PAYMENT, BookingStatus.EXPIRED)
    if not eligible or not await resource_available(db, booking, now):
        booking.payment_review_required = True
        if booking.booking_status == BookingStatus.PENDING_PAYMENT:
            booking.booking_status = BookingStatus.EXPIRED
        attempt.reconciliation_state = "PAYMENT_REVIEW_REQUIRED"
        return
    booking.booking_status = BookingStatus.CONFIRMED
    booking.payment_review_required = False
    attempt.reconciliation_state = "CONFIRMED"
    await db.execute(
        update(Customer)
        .where(
            Customer.id == booking.customer_id,
            Customer.merchant_id == booking.merchant_id,
        )
        .values(total_bookings_count=Customer.total_bookings_count + 1)
    )


async def record_anomaly(db: AsyncSession, attempt: PaymentTransaction, payment_id: str) -> None:
    await db.execute(
        insert(PaymentCaptureAnomaly)
        .values(
            transaction_id=attempt.id,
            provider_payment_id=payment_id,
            amount=attempt.amount,
            currency=attempt.currency,
            reason="DUPLICATE_CAPTURE_REVIEW",
        )
        .on_conflict_do_nothing(constraint="uq_capture_anomaly_payment")
    )
