"""Subscription entitlement and Razorpay protocol helpers.

Only the billing API calls Razorpay; importing this module never makes a request.
"""

import hashlib
import hmac
import math
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.clock import require_aware_utc
from app.core.config import Settings
from app.core.exceptions import AppError
from app.models import Merchant

RAZORPAY_API = "https://api.razorpay.com/v1"


def billing_summary(merchant: Merchant, now: datetime) -> dict[str, Any]:
    now = require_aware_utc(now)
    trial_end = require_aware_utc(merchant.trial_ends_at)
    period_end = (
        require_aware_utc(merchant.current_period_end) if merchant.current_period_end else None
    )
    status = merchant.subscription_status
    if status == "trialing" and now >= trial_end:
        status = "expired"
    elif status == "active" and (period_end is None or now >= period_end):
        status = "past_due"
    if status == "trialing":
        locked = False
    elif status == "active":
        locked = False
    elif status == "cancelled":
        locked = now >= (period_end or trial_end)
    else:
        locked = True
    return {
        "effective_status": status,
        "trial_ends_at": trial_end,
        "days_left": max(0, math.ceil((trial_end - now).total_seconds() / 86400))
        if status == "trialing" else 0,
        "current_period_end": period_end,
        "cancel_at_period_end": merchant.cancel_at_period_end,
        "locked": locked,
        "authorization_confirmed": merchant.checkout_confirmed_at is not None
        or merchant.subscription_authenticated_at is not None,
        "processing": merchant.checkout_confirmed_at is not None
        and merchant.subscription_authenticated_at is None and now >= trial_end,
    }


def require_billing_config(settings: Settings) -> None:
    if not all((settings.razorpay_key_id, settings.razorpay_key_secret,
                settings.razorpay_webhook_secret, settings.razorpay_plan_id)):
        raise AppError("BILLING_UNAVAILABLE", "Billing is not configured", 503)
    expected = "rzp_live_" if settings.environment.lower() == "production" else "rzp_test_"
    if not settings.razorpay_key_id.startswith(expected):
        raise AppError("BILLING_UNAVAILABLE", "Billing is not configured for this environment", 503)


def subscription_payload(merchant: Merchant, settings: Settings, now: datetime) -> dict[str, Any]:
    """Use a five-minute margin so a nearly elapsed trial does not send a past start_at."""
    data: dict[str, Any] = {
        "plan_id": settings.razorpay_plan_id,
        "total_count": settings.billing_total_count,
        "quantity": 1,
        "customer_notify": 1,
        "notes": {"merchant_id": str(merchant.id)},
    }
    if require_aware_utc(merchant.trial_ends_at) > require_aware_utc(now) + timedelta(minutes=5):
        data["start_at"] = int(merchant.trial_ends_at.timestamp())
    return data


def verify_checkout_signature(
    secret: str, payment_id: str, server_subscription_id: str, signature: str
) -> bool:
    message = f"{payment_id}|{server_subscription_id}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(secret: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def validate_plan(plan: dict[str, Any], settings: Settings) -> bool:
    item = plan.get("item")
    return (
        plan.get("id") == settings.razorpay_plan_id
        and plan.get("period") == "monthly"
        and plan.get("interval") == 1
        and isinstance(item, dict)
        and item.get("amount") == settings.billing_plan_amount_paise
        and item.get("currency") == "INR"
    )


async def razorpay_request(
    settings: Settings, method: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    require_billing_config(settings)
    try:
        async with httpx.AsyncClient(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret.get_secret_value()),
            timeout=httpx.Timeout(10.0),
        ) as client:
            response = await client.request(method, f"{RAZORPAY_API}{path}", json=payload)
    except httpx.RequestError as exc:
        raise AppError("BILLING_UNAVAILABLE", "Billing provider is unavailable", 503) from exc
    if not response.is_success:
        # Razorpay responses may reflect request data. Do not include their body in logs or errors.
        raise AppError(
            "BILLING_UNAVAILABLE", "Billing provider could not complete the request", 503
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise AppError(
            "BILLING_UNAVAILABLE", "Billing provider returned an invalid response", 503
        ) from exc
    if not isinstance(data, dict):
        raise AppError("BILLING_UNAVAILABLE", "Billing provider returned an invalid response", 503)
    return data
