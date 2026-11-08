import asyncio
import hashlib
import hmac
import json
from datetime import time, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.api.dependencies import get_clock
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.models import BatchSchedule, Booking, Customer, MerchantPaymentConfig, PaymentTransaction
from app.models.enums import BookingMode, BookingStatus
from app.phase2_main import app
from app.services.payments.gateway import AmbiguousOrder, RazorpayGateway, get_gateway
from app.services.payments.security import decrypt, encrypt, to_paise
from tests.conftest import FIXED_NOW
from tests.helpers import assign, merchant, monday_hours, service, staff
from tests.test_booking_engine import booking_payload

SECRET = "test_secret_123456789"
WEBHOOK_SECRET = "test_webhook_secret_123456789"


class FakeGateway(RazorpayGateway):
    def __init__(self):
        self.orders = {}
        self.payments = {}
        self.calls = 0
        self.timeout = False
        self.unavailable = False
        self.delay = 0

    async def validate_credentials(self, key_id, secret):
        assert key_id.startswith("rzp_test_")

    async def create_order(self, key_id, secret, amount, currency, receipt):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.timeout:
            raise AmbiguousOrder()
        value = {
            "id": f"order_{self.calls}",
            "amount": to_paise(amount),
            "amount_paid": 0,
            "currency": currency,
            "receipt": receipt,
            "status": "created",
        }
        self.orders[value["id"]] = value
        return value.copy()

    async def fetch_order(self, key_id, secret, order_id):
        if self.unavailable:
            raise AppError("PAYMENT_PROVIDER_UNAVAILABLE", "Unavailable", 503)
        return self.orders[order_id].copy()

    async def fetch_payment(self, key_id, secret, payment_id):
        return self.payments[payment_id].copy()

    async def find_order(self, key_id, secret, receipt):
        return next((o.copy() for o in self.orders.values() if o["receipt"] == receipt), None)

    async def order_payments(self, key_id, secret, order_id):
        return {"items": [p.copy() for p in self.payments.values() if p["order_id"] == order_id]}

    def capture(self, order_id, payment_id="pay_success"):
        order = self.orders[order_id]
        order.update(status="paid", amount_paid=order["amount"])
        payment = {
            "id": payment_id,
            "order_id": order_id,
            "status": "captured",
            "captured": True,
            "amount": order["amount"],
            "currency": "INR",
        }
        self.payments[payment_id] = payment
        return payment


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    value = FakeGateway()
    app.dependency_overrides[get_gateway] = lambda: value
    yield value
    app.dependency_overrides.pop(get_gateway, None)
    get_settings.cache_clear()


async def setup_hold(db, client, mode=BookingMode.APPOINTMENT, advance="300.00"):
    owner = await merchant(db)
    offering = await service(
        db,
        owner.id,
        mode=mode,
        capacity=1 if mode == BookingMode.BATCH else None,
        lead_hours=0 if mode == BookingMode.CUSTOM_ORDER else None,
        advance=advance,
    )
    db.add(monday_hours(owner.id))
    payload = booking_payload(str(offering.id))
    if mode == BookingMode.APPOINTMENT:
        member = await staff(db, owner.id, "Asha")
        db.add(assign(offering, member))
        payload["staff_member_id"] = str(member.id)
    elif mode == BookingMode.BATCH:
        batch = BatchSchedule(
            merchant_id=owner.id,
            service_id=offering.id,
            day_of_week=1,
            start_time=time(10),
            end_time=time(11),
            max_capacity=1,
            is_active=True,
        )
        db.add(batch)
        await db.flush()
        payload.pop("start_time")
        payload["batch_schedule_id"] = str(batch.id)
    else:
        payload["end_time"] = "11:00"
    config = MerchantPaymentConfig(
        merchant_id=owner.id,
        key_id="rzp_test_123",
        key_secret_encrypted=encrypt(SECRET),
        webhook_secret_encrypted=encrypt(WEBHOOK_SECRET),
        is_current=True,
        is_enabled=True,
    )
    db.add(config)
    await db.commit()
    response = await client.post("/api/v1/bookings/initiate", json=payload)
    assert response.status_code == 201, response.text
    hold = response.json()
    return owner, config, hold, payload


def headers(hold):
    return {"X-Booking-Token": hold["public_booking_token"]}


async def create_order(client, hold):
    response = await client.post(
        f"/api/v1/bookings/{hold['booking_reference']}/payment", headers=headers(hold)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def webhook(client, config, payment, event_type="payment.captured", event_id="ev_capture"):
    raw = json.dumps({"event": event_type, "payload": {"payment": {"entity": payment}}}).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    webhook_id = getattr(config, "webhook_id", config)
    return await client.post(
        f"/api/v1/payments/razorpay/webhook/{webhook_id}",
        content=raw,
        headers={"X-Razorpay-Signature": signature, "x-razorpay-event-id": event_id},
    )


async def verify(client, hold, order_id, payment_id="pay_success"):
    signature = hmac.new(
        SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    return await client.post(
        "/api/v1/payments/razorpay/verify",
        headers=headers(hold),
        json={
            "booking_reference": hold["booking_reference"],
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        },
    )


@pytest.mark.parametrize("mode", list(BookingMode))
async def test_all_modes_capture_race_exactly_once(client, db, gateway, mode):
    _, config, hold, _ = await setup_hold(db, client, mode)
    order = await create_order(client, hold)
    payment = gateway.capture(order["order_id"])
    responses = await asyncio.gather(
        webhook(client, config, payment),
        webhook(client, config, payment),
        verify(client, hold, order["order_id"]),
    )
    assert [r.status_code for r in responses] == [200, 200, 200]
    status = await client.get(
        f"/api/v1/bookings/{hold['booking_reference']}/status", headers=headers(hold)
    )
    assert status.headers["cache-control"] == "no-store, private"
    assert status.json()["booking_status"] == "CONFIRMED"
    assert status.json()["amount_paid"] == "300.00"
    assert status.json()["balance_due"] == "1200.00"
    assert "customer_phone" not in status.text and "public_booking_token" not in status.text
    await db.rollback()
    customer = await db.scalar(select(Customer))
    assert customer.total_bookings_count == 1 and customer.last_visit_date is None
    attempt = await db.scalar(select(PaymentTransaction))
    assert attempt.status == "CAPTURED" and attempt.provider_payment_id == "pay_success"
    again = await client.post(
        f"/api/v1/bookings/{hold['booking_reference']}/payment", headers=headers(hold)
    )
    assert again.status_code == 409 and gateway.calls == 1


async def test_failed_then_captured_other_payment_and_no_downgrade(client, db, gateway):
    _, config, hold, _ = await setup_hold(db, client, advance="0.00")
    order = await create_order(client, hold)
    failed = {
        "id": "pay_failed",
        "order_id": order["order_id"],
        "status": "failed",
        "error_code": "BAD_REQUEST_ERROR",
        "error_reason": "pii@example.com",
    }
    assert (await webhook(client, config, failed, "payment.failed", "ev_fail")).status_code == 200
    await db.rollback()
    attempt = await db.scalar(select(PaymentTransaction))
    assert attempt.status == "FAILED" and attempt.provider_payment_id is None
    assert attempt.failure_reason is None
    gateway.orders[order["order_id"]]["status"] = "attempted"
    assert (await create_order(client, hold))["order_id"] == order["order_id"]
    payment = gateway.capture(order["order_id"])
    assert (await webhook(client, config, payment)).status_code == 200
    assert (
        await webhook(client, config, failed, "payment.failed", "ev_fail_late")
    ).status_code == 200
    await db.rollback()
    attempt = await db.scalar(select(PaymentTransaction).execution_options(populate_existing=True))
    assert attempt.status == "CAPTURED"
    booking = await db.scalar(select(Booking))
    assert booking.balance_due == 0 and gateway.calls == 1


async def test_duplicate_creation_and_unknown_timeout_block_replacement(client, db, gateway):
    _, _, hold, _ = await setup_hold(db, client)
    gateway.delay = 1
    gateway.timeout = True
    url = f"/api/v1/bookings/{hold['booking_reference']}/payment"
    responses = await asyncio.gather(
        client.post(url, headers=headers(hold)), client.post(url, headers=headers(hold))
    )
    assert sorted(r.status_code for r in responses) == [409, 503]
    assert gateway.calls == 1
    assert (await client.post(url, headers=headers(hold))).status_code == 503
    assert gateway.calls == 1
    await db.rollback()
    attempt = await db.scalar(select(PaymentTransaction))
    assert attempt.status == "UNKNOWN"
    gateway.orders["order_recovered"] = {
        "id": "order_recovered",
        "amount": to_paise(attempt.amount),
        "amount_paid": 0,
        "currency": "INR",
        "receipt": attempt.receipt,
        "status": "created",
    }
    assert (await create_order(client, hold))["order_id"] == "order_recovered"
    assert gateway.calls == 1


@pytest.mark.parametrize("mode", [BookingMode.APPOINTMENT, BookingMode.BATCH])
async def test_expired_hold_resource_taken_requires_review(client, db, gateway, mode):
    _, config, hold, payload = await setup_hold(db, client, mode)
    order = await create_order(client, hold)
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW + timedelta(minutes=11)
    payload["customer_phone"] = "9876543222"
    assert (await client.post("/api/v1/bookings/initiate", json=payload)).status_code == 201
    payment = gateway.capture(order["order_id"])
    assert (await webhook(client, config, payment)).status_code == 200
    status = (
        await client.get(
            f"/api/v1/bookings/{hold['booking_reference']}/status", headers=headers(hold)
        )
    ).json()
    assert status["payment_review_required"] and status["booking_status"] == "EXPIRED"
    assert status["amount_paid"] == "300.00"
    await db.rollback()
    assert await db.scalar(select(func.sum(Customer.total_bookings_count))) == 0


async def test_signature_before_parsing_transient_retry_and_token_isolation(client, db, gateway):
    _, config, hold, _ = await setup_hold(db, client)
    url = f"/api/v1/bookings/{hold['booking_reference']}/status"
    assert (await client.get(url)).status_code == 404
    assert (await client.get(url, headers={"X-Booking-Token": "wrong"})).status_code == 404
    response = await client.post(
        f"/api/v1/payments/razorpay/webhook/{config.webhook_id}",
        content=b"not json",
        headers={"X-Razorpay-Signature": "wrong"},
    )
    assert response.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"
    order = await create_order(client, hold)
    payment = gateway.capture(order["order_id"])
    gateway.unavailable = True
    assert (await webhook(client, config, payment)).status_code == 503
    gateway.unavailable = False
    assert (await webhook(client, config, payment)).status_code == 200


async def test_settings_rotation_disconnect_and_redaction(client, db, gateway):
    owner, old_config, hold, _ = await setup_hold(db, client)
    order = await create_order(client, hold)
    auth = {"Authorization": f"Bearer {create_access_token(owner.id)}"}
    settings_url = "/api/v1/merchants/me/payment-settings"
    payload = {
        "mode": "LIVE",
        "key_id": "rzp_live_123",
        "key_secret": SECRET,
        "webhook_secret": WEBHOOK_SECRET,
    }
    rejected = await client.put(settings_url, headers=auth, json=payload)
    assert rejected.status_code == 400 and SECRET not in rejected.text
    payload.update(
        mode="TEST",
        key_id="rzp_test_new",
        key_secret=SECRET + "_rotated",
        webhook_secret=WEBHOOK_SECRET + "_rotated",
    )
    rotated = await client.put(settings_url, headers=auth, json=payload)
    assert rotated.status_code == 200, rotated.text
    assert SECRET not in rotated.text and "rzp_test_new" not in rotated.text
    assert (await client.delete(settings_url, headers=auth)).status_code == 200
    assert (
        await client.post(
            f"/api/v1/bookings/{hold['booking_reference']}/payment", headers=headers(hold)
        )
    ).status_code == 409
    payment = gateway.capture(order["order_id"])
    assert (await webhook(client, old_config, payment)).status_code == 200
    await db.rollback()
    configs = list(await db.scalars(select(MerchantPaymentConfig)))
    assert len(configs) == 2
    assert {decrypt(c.key_secret_encrypted) for c in configs} == {SECRET, SECRET + "_rotated"}
    other = await merchant(db, slug="other", email="other@example.com")
    await db.commit()
    other_auth = {"Authorization": f"Bearer {create_access_token(other.id)}"}
    assert (await client.get("/api/v1/merchants/me/bookings", headers=other_auth)).json() == []


async def test_capture_mismatches_do_not_confirm_then_valid_capture_succeeds(client, db, gateway):
    _, config, hold, _ = await setup_hold(db, client)
    order = await create_order(client, hold)
    original = gateway.capture(order["order_id"])
    for index, changes in enumerate(
        [
            {"amount": original["amount"] + 1},
            {"currency": "USD"},
            {"captured": False},
            {"status": "authorized"},
        ]
    ):
        response = await webhook(client, config, original | changes, event_id=f"ev_bad_{index}")
        assert response.status_code == 200
        status = (
            await client.get(
                f"/api/v1/bookings/{hold['booking_reference']}/status",
                headers=headers(hold),
            )
        ).json()
        assert status["booking_status"] == "PENDING_PAYMENT" and status["amount_paid"] == "0.00"
    wrong_order = original | {"order_id": "order_foreign"}
    assert (await webhook(client, config, wrong_order, event_id="ev_foreign")).status_code == 503
    assert (await webhook(client, config, original, event_id="ev_good")).status_code == 200


async def test_expired_available_hold_paid_order_reconciles_without_new_order(client, db, gateway):
    _, config, hold, _ = await setup_hold(db, client)
    order = await create_order(client, hold)
    payment = gateway.capture(order["order_id"])
    # Paid order fetch provides synchronous confirmation even before webhook arrival.
    reconciled = await create_order(client, hold)
    assert reconciled == {"state": "RECONCILED"} and gateway.calls == 1
    assert (await webhook(client, config, payment)).status_code == 200


@pytest.mark.parametrize("cancelled", [False, True])
async def test_late_capture_free_resource_or_cancelled(client, db, gateway, cancelled):
    _, config, hold, _ = await setup_hold(db, client)
    order = await create_order(client, hold)
    if cancelled:
        booking = await db.scalar(select(Booking))
        booking.booking_status = BookingStatus.CANCELLED
        await db.commit()
    app.dependency_overrides[get_clock] = lambda: lambda: FIXED_NOW + timedelta(minutes=11)
    assert (await webhook(client, config, gateway.capture(order["order_id"]))).status_code == 200
    status = (
        await client.get(
            f"/api/v1/bookings/{hold['booking_reference']}/status",
            headers=headers(hold),
        )
    ).json()
    assert status["booking_status"] == ("CANCELLED" if cancelled else "CONFIRMED")
    assert status["payment_review_required"] == cancelled


async def test_webhook_header_precedence_fallback_and_ignored_events(client, db, gateway):
    _, config, hold, _ = await setup_hold(db, client)
    order = await create_order(client, hold)
    payment = gateway.capture(order["order_id"])
    raw = json.dumps(
        {"event": "payment.captured", "payload": {"payment": {"entity": payment}}}
    ).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    url = f"/api/v1/payments/razorpay/webhook/{config.webhook_id}"
    for _ in range(2):
        assert (
            await client.post(url, content=raw, headers={"X-Razorpay-Signature": signature})
        ).status_code == 200
    assert (await webhook(client, config, payment, "unused.event", "ev_ignored")).status_code == 200
    # Event ID has precedence over different signed bytes for duplicate deliveries.
    assert (await webhook(client, config, payment, "unused.other", "ev_ignored")).status_code == 200
    raw_ignored = b'{"event":"unused.shape","payload":null}'
    ignored_signature = hmac.new(WEBHOOK_SECRET.encode(), raw_ignored, hashlib.sha256).hexdigest()
    assert (
        await client.post(
            url,
            content=raw_ignored,
            headers={
                "X-Razorpay-Signature": ignored_signature,
            },
        )
    ).status_code == 200
    await db.rollback()
    assert (await db.scalar(select(Customer))).total_bookings_count == 1


async def test_transient_processing_rolls_back_event_then_retry_succeeds(
    client, db, gateway, monkeypatch
):
    from app.models import PaymentWebhookEvent
    from app.services.payments import webhooks

    _, config, hold, _ = await setup_hold(db, client)
    webhook_id = config.webhook_id
    order = await create_order(client, hold)
    payment = gateway.capture(order["order_id"])
    original = webhooks.reconcile_locked

    async def temporarily_unavailable(*args, **kwargs):
        raise AppError("TEMPORARY_FAILURE", "Temporary processing failure", 503)

    monkeypatch.setattr(webhooks, "reconcile_locked", temporarily_unavailable)
    assert (await webhook(client, webhook_id, payment)).status_code == 503
    await db.rollback()
    assert await db.scalar(select(func.count(PaymentWebhookEvent.id))) == 0
    await db.rollback()
    monkeypatch.setattr(webhooks, "reconcile_locked", original)
    assert (await webhook(client, webhook_id, payment)).status_code == 200


async def test_duplicate_capture_preserves_separate_financial_evidence(client, db, gateway):
    from app.models import PaymentCaptureAnomaly

    _, config, hold, _ = await setup_hold(db, client)
    order = await create_order(client, hold)
    first = gateway.capture(order["order_id"])
    assert (await webhook(client, config, first)).status_code == 200
    second = gateway.capture(order["order_id"], "pay_anomaly")
    assert (await verify(client, hold, order["order_id"], "pay_anomaly")).status_code == 200
    assert (await webhook(client, config, second, event_id="ev_second_capture")).status_code == 200
    await db.rollback()
    attempt = await db.scalar(select(PaymentTransaction))
    assert attempt.provider_payment_id == "pay_success"
    assert attempt.reconciliation_state == "DUPLICATE_CAPTURE_REVIEW"
    anomaly = await db.scalar(select(PaymentCaptureAnomaly))
    assert anomaly.provider_payment_id == "pay_anomaly" and anomaly.amount == attempt.amount
    assert await db.scalar(select(func.count(PaymentCaptureAnomaly.id))) == 1
    assert (await db.scalar(select(Customer))).total_bookings_count == 1


async def test_hold_expiry_during_order_creation_does_not_launch_checkout(client, db, gateway):
    _, _, hold, _ = await setup_hold(db, client)
    current = [FIXED_NOW]
    app.dependency_overrides[get_clock] = lambda: lambda: current[0]
    original = gateway.create_order

    async def delayed_order(*args):
        order = await original(*args)
        current[0] = FIXED_NOW + timedelta(minutes=11)
        return order

    gateway.create_order = delayed_order
    response = await client.post(
        f"/api/v1/bookings/{hold['booking_reference']}/payment",
        headers=headers(hold),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BOOKING_NOT_PAYABLE"
    await db.rollback()
    attempt = await db.scalar(select(PaymentTransaction))
    assert attempt.provider_order_id == "order_1" and gateway.calls == 1
