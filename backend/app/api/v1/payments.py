from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select, update

from app.api.dependencies import CurrentClock, CurrentMerchant, DatabaseSession
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import (
    Booking,
    Merchant,
    MerchantPaymentConfig,
    PaymentTransaction,
    Service,
    StaffMember,
)
from app.services.payments.gateway import RazorpayGateway, get_gateway
from app.services.payments.orders import lock_attempt, payable_order, public_booking
from app.services.payments.reconciliation import reconcile_locked
from app.services.payments.security import decrypt, encrypt, verify_signature
from app.services.payments.webhooks import process_webhook

router = APIRouter(tags=["payments"])
Gateway = Annotated[RazorpayGateway, Depends(get_gateway)]
BookingToken = Annotated[str, Header(alias="X-Booking-Token", max_length=128)]


class PaymentSettingsInput(BaseModel):
    mode: Literal["TEST"] = "TEST"
    key_id: str = Field(pattern=r"^rzp_test_[A-Za-z0-9]+$", max_length=100)
    key_secret: SecretStr = Field(min_length=8, max_length=200)
    webhook_secret: SecretStr = Field(min_length=16, max_length=200)


class CheckoutVerification(BaseModel):
    booking_reference: str = Field(max_length=32)
    razorpay_order_id: str = Field(pattern=r"^order_[A-Za-z0-9]+$", max_length=100)
    razorpay_payment_id: str = Field(pattern=r"^pay_[A-Za-z0-9]+$", max_length=100)
    razorpay_signature: SecretStr = Field(min_length=64, max_length=64)


def masked_settings(config: MerchantPaymentConfig | None) -> dict:
    if config is None:
        return {"configured": False, "enabled": False, "mode": "TEST"}
    return {
        "configured": True,
        "enabled": config.is_enabled,
        "mode": config.mode,
        "key_id_masked": f"rzp_test_…{config.key_id[-4:]}",
        "webhook_url": f"{get_settings().public_api_url.rstrip('/')}"
        f"/api/v1/payments/razorpay/webhook/{config.webhook_id}",
        "config_id": str(config.id),
        "created_at": config.created_at,
    }


@router.get("/merchants/me/payment-settings")
async def payment_settings(merchant: CurrentMerchant, db: DatabaseSession, response: Response):
    response.headers["Cache-Control"] = "no-store"
    config = await db.scalar(
        select(MerchantPaymentConfig).where(
            MerchantPaymentConfig.merchant_id == merchant.id,
            MerchantPaymentConfig.is_current.is_(True),
        )
    )
    return masked_settings(config)


@router.put("/merchants/me/payment-settings")
async def save_settings(
    payload: PaymentSettingsInput,
    merchant: CurrentMerchant,
    db: DatabaseSession,
    gateway: Gateway,
):
    merchant_id = merchant.id
    # Encrypt/validate before obtaining the serialization lock or changing current credentials.
    encrypted_key = encrypt(payload.key_secret.get_secret_value())
    encrypted_webhook = encrypt(payload.webhook_secret.get_secret_value())
    await db.commit()
    await gateway.validate_credentials(payload.key_id, payload.key_secret.get_secret_value())
    await db.scalar(select(Merchant).where(Merchant.id == merchant_id).with_for_update())
    await db.execute(
        update(MerchantPaymentConfig)
        .where(
            MerchantPaymentConfig.merchant_id == merchant_id,
            MerchantPaymentConfig.is_current.is_(True),
        )
        .values(is_current=False, is_enabled=False)
    )
    config = MerchantPaymentConfig(
        merchant_id=merchant_id,
        mode="TEST",
        key_id=payload.key_id,
        key_secret_encrypted=encrypted_key,
        webhook_secret_encrypted=encrypted_webhook,
        is_current=True,
        is_enabled=True,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return masked_settings(config)


@router.delete("/merchants/me/payment-settings")
async def disconnect(merchant: CurrentMerchant, db: DatabaseSession):
    await db.scalar(select(Merchant).where(Merchant.id == merchant.id).with_for_update())
    await db.execute(
        update(MerchantPaymentConfig)
        .where(
            MerchantPaymentConfig.merchant_id == merchant.id,
            MerchantPaymentConfig.is_current.is_(True),
        )
        .values(is_enabled=False)
    )
    await db.commit()
    return {"enabled": False}


@router.post("/bookings/{reference}/payment")
async def create_payment(
    reference: str,
    db: DatabaseSession,
    clock: CurrentClock,
    gateway: Gateway,
    response: Response,
    x_booking_token: BookingToken = "",
):
    response.headers["Cache-Control"] = "no-store"
    return await payable_order(db, reference, x_booking_token, clock, gateway)


@router.post("/payments/razorpay/verify")
async def verify_checkout(
    payload: CheckoutVerification,
    db: DatabaseSession,
    clock: CurrentClock,
    gateway: Gateway,
    response: Response,
    x_booking_token: BookingToken = "",
):
    response.headers["Cache-Control"] = "no-store"
    booking = await public_booking(db, payload.booking_reference, x_booking_token)
    attempt = await db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.booking_id == booking.id,
            PaymentTransaction.merchant_id == booking.merchant_id,
            PaymentTransaction.provider_order_id == payload.razorpay_order_id,
        )
    )
    if attempt is None:
        raise AppError("NOT_FOUND", "Payment not found", 404)
    config = await db.get(MerchantPaymentConfig, attempt.config_id)
    secret = decrypt(config.key_secret_encrypted)
    verify_signature(
        f"{attempt.provider_order_id}|{payload.razorpay_payment_id}".encode(),
        payload.razorpay_signature.get_secret_value(),
        secret,
        "PAYMENT_SIGNATURE_INVALID",
    )
    await db.commit()
    payment = await gateway.fetch_payment(config.key_id, secret, payload.razorpay_payment_id)
    order = await gateway.fetch_order(config.key_id, secret, attempt.provider_order_id)
    if payment.get("id") != payload.razorpay_payment_id:
        raise AppError("PAYMENT_STATE_MISMATCH", "Provider payment identity mismatch", 409)
    if payment.get("status") != "captured":
        return {"state": "PROCESSING"}
    booking = await public_booking(db, payload.booking_reference, x_booking_token, lock=True)
    attempt = await lock_attempt(db, attempt.id)
    await reconcile_locked(db, booking, attempt, payment, order, clock())
    await db.commit()
    return {"state": "RECONCILED"}


@router.post("/payments/razorpay/webhook/{opaque_config_id}")
async def webhook(
    opaque_config_id: UUID,
    request: Request,
    db: DatabaseSession,
    clock: CurrentClock,
    gateway: Gateway,
):
    raw = await request.body()
    if len(raw) > 1_000_000:
        raise AppError("WEBHOOK_PAYLOAD_INVALID", "Webhook payload too large", 413)
    await process_webhook(
        db,
        opaque_config_id,
        raw,
        request.headers.get("x-razorpay-signature", ""),
        request.headers.get("x-razorpay-event-id"),
        clock,
        gateway,
    )
    return {"received": True}


async def booking_summary(db, booking: Booking) -> dict:
    merchant = await db.get(Merchant, booking.merchant_id)
    service = await db.get(Service, booking.service_id)
    staff = await db.get(StaffMember, booking.staff_member_id) if booking.staff_member_id else None
    return {
        "merchant_name": merchant.business_name,
        "service_name": service.title,
        "booking_mode": service.booking_mode,
        "booking_date": booking.booking_date,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "staff_name": staff.name if staff else None,
        "booking_status": booking.booking_status,
        "payment_status": booking.payment_status,
        "amount_paid": format(booking.amount_paid, ".2f"),
        "balance_due": format(booking.balance_due, ".2f"),
        "hold_expires_at": booking.hold_expires_at,
        "payment_review_required": booking.payment_review_required,
    }


@router.get("/bookings/{reference}/status")
async def booking_status(
    reference: str,
    db: DatabaseSession,
    response: Response,
    x_booking_token: BookingToken = "",
):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    booking = await public_booking(db, reference, x_booking_token)
    return await booking_summary(db, booking)


@router.get("/merchants/me/bookings")
async def recent_bookings(merchant: CurrentMerchant, db: DatabaseSession, response: Response):
    response.headers["Cache-Control"] = "no-store"
    bookings = await db.scalars(
        select(Booking)
        .where(
            Booking.merchant_id == merchant.id,
        )
        .order_by(Booking.created_at.desc(), Booking.id.desc())
        .limit(50)
    )
    summaries = []
    for booking in bookings:
        attempt = await db.scalar(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.booking_id == booking.id,
                PaymentTransaction.merchant_id == merchant.id,
            )
            .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
            .limit(1)
        )
        summaries.append(
            {
                "booking_reference": booking.booking_reference,
                **await booking_summary(db, booking),
                "provider_status": attempt.status if attempt else None,
                "receipt": attempt.receipt if attempt else None,
                "reconciliation_state": attempt.reconciliation_state if attempt else None,
                "failure_code": attempt.failure_code if attempt else None,
                "failure_reason": attempt.failure_reason if attempt else None,
            }
        )
    return summaries
