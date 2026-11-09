"""Authenticated merchant subscription billing API."""

from datetime import UTC, datetime

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.dependencies import CurrentClock, CurrentMerchant, DatabaseSession
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import BillingPayment, Merchant
from app.schemas.billing import (
    BillingActionResponse,
    BillingDetail,
    BillingPaymentOut,
    BillingSummary,
    ConfirmRequest,
    SubscribeResponse,
)
from app.services.billing_service import (
    billing_summary,
    razorpay_request,
    require_billing_config,
    subscription_payload,
    validate_plan,
    verify_checkout_signature,
)

router = APIRouter(prefix="/billing", tags=["billing"])


def _no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("", response_model=BillingDetail)
async def get_billing(
    merchant: CurrentMerchant, db: DatabaseSession, clock: CurrentClock, response: Response
) -> BillingDetail:
    _no_cache(response)
    payments = list(await db.scalars(
        select(BillingPayment).where(BillingPayment.merchant_id == merchant.id)
        .order_by(BillingPayment.created_at.desc(), BillingPayment.id.desc()).limit(12)
    ))
    return BillingDetail(
        summary=BillingSummary.model_validate(billing_summary(merchant, clock())),
        payments=[BillingPaymentOut.model_validate(payment) for payment in payments],
    )


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    merchant: CurrentMerchant, db: DatabaseSession, clock: CurrentClock, response: Response
) -> SubscribeResponse:
    _no_cache(response)
    settings = get_settings()
    require_billing_config(settings)
    locked_merchant = await db.scalar(
        select(Merchant).where(Merchant.id == merchant.id).with_for_update()
    )
    if locked_merchant is None:
        raise AppError("AUTHENTICATION_REQUIRED", "Merchant account is unavailable", 401)
    if (
        locked_merchant.subscription_status == "cancelled"
        and locked_merchant.current_period_end is not None
        and locked_merchant.current_period_end > clock()
    ):
        raise AppError(
            "BILLING_PERIOD_ACTIVE",
            "Your paid period is still active; subscribe after it ends",
            409,
        )
    if (
        locked_merchant.razorpay_subscription_id
        and locked_merchant.subscription_status not in ("cancelled", "expired")
    ):
        current = await razorpay_request(
            settings, "GET", f"/subscriptions/{locked_merchant.razorpay_subscription_id}"
        )
        if current.get("status") in (
            "created", "authenticated", "active", "pending", "halted", "paused", "resumed"
        ):
            return SubscribeResponse(
                subscription_id=locked_merchant.razorpay_subscription_id,
                key_id=settings.razorpay_key_id,
            )
        if current.get("status") not in ("cancelled", "completed", "expired"):
            raise AppError("BILLING_UNAVAILABLE", "Subscription status could not be verified", 503)
    plan = await razorpay_request(settings, "GET", f"/plans/{settings.razorpay_plan_id}")
    if not validate_plan(plan, settings):
        raise AppError("BILLING_PLAN_MISMATCH", "The billing plan needs verification", 503)
    created = await razorpay_request(
        settings, "POST", "/subscriptions", subscription_payload(locked_merchant, settings, clock())
    )
    subscription_id = created.get("id")
    if (
        not isinstance(subscription_id, str)
        or not subscription_id.startswith("sub_")
        or created.get("plan_id") != settings.razorpay_plan_id
    ):
        raise AppError("BILLING_UNAVAILABLE", "Billing provider returned an invalid response", 503)
    locked_merchant.razorpay_subscription_id = subscription_id
    locked_merchant.cancel_at_period_end = False
    locked_merchant.checkout_confirmed_at = None
    locked_merchant.subscription_authenticated_at = None
    # A new subscription does not grant access until Razorpay confirms its first cycle.
    locked_merchant.subscription_status = (
        "trialing" if clock() < locked_merchant.trial_ends_at else "expired"
    )
    locked_merchant.current_period_end = None
    await db.commit()
    return SubscribeResponse(subscription_id=subscription_id, key_id=settings.razorpay_key_id)


@router.post("/confirm", response_model=BillingActionResponse)
async def confirm(
    payload: ConfirmRequest,
    merchant: CurrentMerchant,
    db: DatabaseSession,
    response: Response,
) -> BillingActionResponse:
    _no_cache(response)
    settings = get_settings()
    require_billing_config(settings)
    if not merchant.razorpay_subscription_id or (
        payload.razorpay_subscription_id != merchant.razorpay_subscription_id
    ):
        raise AppError("BILLING_CONFIRMATION_INVALID", "Subscription confirmation is invalid", 400)
    if not verify_checkout_signature(
        settings.razorpay_key_secret.get_secret_value(),
        payload.razorpay_payment_id,
        merchant.razorpay_subscription_id,
        payload.razorpay_signature,
    ):
        raise AppError("BILLING_CONFIRMATION_INVALID", "Subscription confirmation is invalid", 400)
    if merchant.subscription_authenticated_at is None:
        merchant.checkout_confirmed_at = datetime.now(UTC)
    await db.commit()
    # The webhook, not Checkout, controls entitlement and the effective status.
    return BillingActionResponse(
        status="authorized" if (
            merchant.subscription_authenticated_at or merchant.trial_ends_at > datetime.now(UTC)
        ) else "processing"
    )


@router.post("/cancel", response_model=BillingActionResponse)
async def cancel(
    merchant: CurrentMerchant, db: DatabaseSession, clock: CurrentClock, response: Response
) -> BillingActionResponse:
    _no_cache(response)
    settings = get_settings()
    require_billing_config(settings)
    locked_merchant = await db.scalar(
        select(Merchant).where(Merchant.id == merchant.id).with_for_update()
    )
    if locked_merchant is None or not locked_merchant.razorpay_subscription_id:
        raise AppError("BILLING_NOT_FOUND", "There is no subscription to cancel", 404)
    if locked_merchant.cancel_at_period_end:
        return BillingActionResponse(status="cancel_scheduled")
    if (
        locked_merchant.subscription_status != "active"
        or locked_merchant.current_period_end is None
        or locked_merchant.current_period_end <= clock()
    ):
        raise AppError(
            "BILLING_CYCLE_NOT_STARTED",
            "Cycle-end cancellation is available after the first billing cycle starts",
            409,
        )
    result = await razorpay_request(
        settings, "POST",
        f"/subscriptions/{locked_merchant.razorpay_subscription_id}/cancel",
        {"cancel_at_cycle_end": True},
    )
    if result.get("id") != locked_merchant.razorpay_subscription_id:
        raise AppError("BILLING_UNAVAILABLE", "Billing provider returned an invalid response", 503)
    locked_merchant.cancel_at_period_end = True
    await db.commit()
    return BillingActionResponse(status="cancel_scheduled")
