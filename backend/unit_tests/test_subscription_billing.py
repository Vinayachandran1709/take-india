"""Offline subscription billing checks. No provider or database connection is made."""

import hashlib
import hmac
import importlib.util
import json
import secrets
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from fastapi import Response
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.dependencies import get_clock, get_current_merchant, require_billing_access
from app.api.v1 import billing, billing_webhooks, confirmed_bookings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.services.billing_service import (
    billing_summary,
    subscription_payload,
    validate_plan,
    verify_checkout_signature,
    verify_webhook_signature,
)
from app.v1_main import app

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def merchant(**changes):
    values = {
        "id": uuid4(), "trial_ends_at": NOW + timedelta(days=10),
        "subscription_status": "trialing", "current_period_end": None,
        "cancel_at_period_end": False, "checkout_confirmed_at": None,
        "subscription_authenticated_at": None, "razorpay_subscription_id": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_trial_expiry_and_lock_rules():
    assert billing_summary(merchant(), NOW)["days_left"] == 10
    assert billing_summary(merchant(), NOW + timedelta(days=10))["effective_status"] == "expired"
    assert billing_summary(merchant(), NOW + timedelta(days=10))["locked"]
    active = merchant(subscription_status="active", current_period_end=NOW + timedelta(days=30))
    assert not billing_summary(active, NOW)["locked"]
    assert billing_summary(active, NOW + timedelta(days=30))["locked"]
    assert billing_summary(merchant(subscription_status="past_due"), NOW)["locked"]
    cancelled = merchant(
        subscription_status="cancelled", current_period_end=NOW + timedelta(days=1)
    )
    assert not billing_summary(cancelled, NOW)["locked"]
    assert billing_summary(cancelled, NOW + timedelta(days=1))["locked"]


def test_start_at_only_for_safely_future_trial():
    settings = SimpleNamespace(razorpay_plan_id="plan_example", billing_total_count=120)
    future = merchant(trial_ends_at=NOW + timedelta(days=30))
    payload = subscription_payload(future, settings, NOW)
    assert payload["start_at"] == int(future.trial_ends_at.timestamp())
    assert payload["total_count"] == 120
    assert payload["quantity"] == 1
    assert payload["customer_notify"] == 1
    assert "start_at" not in subscription_payload(
        merchant(trial_ends_at=NOW + timedelta(minutes=4)), settings, NOW
    )


def test_checkout_and_raw_body_webhook_signatures():
    secret = secrets.token_hex(32)
    checkout_message = b"pay_example|sub_example"
    checkout_signature = hmac.new(secret.encode(), checkout_message, hashlib.sha256).hexdigest()
    assert verify_checkout_signature(secret, "pay_example", "sub_example", checkout_signature)
    assert not verify_checkout_signature(secret, "pay_tampered", "sub_example", checkout_signature)
    assert not verify_checkout_signature(secret, "pay_example", "sub_example", "0" * 64)
    body = b'{"event":"subscription.activated"}'
    webhook_signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(secret, body, webhook_signature)
    assert not verify_webhook_signature(secret, body + b" ", webhook_signature)
    assert not verify_webhook_signature(secret, body, "0" * 64)


@pytest.mark.parametrize("event,status", [
    ("subscription.authenticated", "trialing"),
    ("subscription.activated", "active"),
    ("subscription.charged", "active"),
    ("subscription.pending", "past_due"),
    ("subscription.halted", "past_due"),
    ("subscription.paused", "past_due"),
    ("subscription.resumed", "active"),
    ("subscription.cancelled", "cancelled"),
    ("subscription.completed", "expired"),
])
def test_each_documented_event_mapping(event, status):
    assert billing_webhooks.EVENT_STATUS[event] == status


def test_out_of_order_events_and_amount_mismatch():
    assert billing_webhooks.is_stale_event(
        NOW, "subscription.authenticated", (NOW + timedelta(seconds=1), "subscription.activated")
    )
    assert billing_webhooks.is_stale_event(
        NOW, "subscription.activated", (NOW, "subscription.charged")
    )
    assert not billing_webhooks.is_stale_event(
        NOW, "subscription.charged", (NOW, "subscription.activated")
    )
    # A captured charge wins over a pending notice when provider timestamps tie.
    assert not billing_webhooks.is_stale_event(
        NOW, "subscription.charged", (NOW, "subscription.pending")
    )
    assert billing_webhooks.is_stale_event(
        NOW, "subscription.pending", (NOW, "subscription.charged")
    )
    payment = {"id": "pay_example", "amount": 149900, "currency": "INR", "status": "captured"}
    assert billing_webhooks.valid_charge(payment, 149900)
    assert not billing_webhooks.valid_charge({**payment, "amount": 149899}, 149900)
    assert not billing_webhooks.valid_charge({**payment, "currency": "USD"}, 149900)
    settings = SimpleNamespace(razorpay_plan_id="plan_example", billing_plan_amount_paise=149900)
    plan = {"id": "plan_example", "period": "monthly", "interval": 1,
            "item": {"amount": 149900, "currency": "INR"}}
    assert validate_plan(plan, settings)
    assert not validate_plan({**plan, "id": "plan_other"}, settings)
    assert not validate_plan({**plan, "item": {"amount": 149899, "currency": "INR"}}, settings)


class WebhookResult:
    def __init__(self, inserted=None, previous=None):
        self.inserted = inserted
        self.previous = previous

    def scalar_one_or_none(self):
        return self.inserted

    def first(self):
        return self.previous


class WebhookDatabase:
    def __init__(self, owner, previous=None):
        self.owner = owner
        self.previous = previous
        self.record = SimpleNamespace()
        self.payment_inserts = 0

    async def execute(self, statement):
        if statement.is_insert and statement.table.name == "billing_webhook_events":
            return WebhookResult(inserted="evt_example")
        if statement.is_insert and statement.table.name == "billing_payments":
            self.payment_inserts += 1
            return WebhookResult()
        return WebhookResult(previous=self.previous)

    async def get(self, _model, _key):
        return self.record

    async def scalar(self, _statement):
        return self.owner


def webhook_data(event, *, plan_id="plan_example", amount=149900):
    payload = {
        "subscription": {"entity": {
            "id": "sub_example", "plan_id": plan_id, "quantity": 1,
            "current_end": int((NOW + timedelta(days=30)).timestamp()),
        }}
    }
    if event == "subscription.charged":
        payload["payment"] = {"entity": {
            "id": "pay_example", "amount": amount, "currency": "INR",
            "status": "captured", "created_at": int(NOW.timestamp()),
        }}
    return {"event": event, "created_at": int(NOW.timestamp()), "payload": payload}


@pytest.mark.parametrize("event,status", list(billing_webhooks.EVENT_STATUS.items()))
async def test_verified_webhook_applies_documented_status(monkeypatch, event, status):
    owner = merchant(razorpay_subscription_id="sub_example")
    db = WebhookDatabase(owner)
    monkeypatch.setattr(billing_webhooks, "get_settings", lambda: SimpleNamespace(
        razorpay_plan_id="plan_example", billing_plan_amount_paise=149900,
    ))
    data = webhook_data(event)
    result = await billing_webhooks.process_verified_event(
        db, "evt_example", json.dumps(data).encode(), data
    )
    assert result == "applied"
    assert owner.subscription_status == status
    assert db.record.processing_status == "applied"
    assert db.payment_inserts == (1 if event == "subscription.charged" else 0)


@pytest.mark.parametrize("event,plan_id,amount,code", [
    ("subscription.activated", "plan_other", 149900, "plan_mismatch"),
    ("subscription.charged", "plan_example", 149899, "amount_mismatch"),
])
async def test_webhook_anomaly_never_activates(monkeypatch, event, plan_id, amount, code):
    owner = merchant(razorpay_subscription_id="sub_example")
    db = WebhookDatabase(owner)
    monkeypatch.setattr(billing_webhooks, "get_settings", lambda: SimpleNamespace(
        razorpay_plan_id="plan_example", billing_plan_amount_paise=149900,
    ))
    data = webhook_data(event, plan_id=plan_id, amount=amount)
    result = await billing_webhooks.process_verified_event(
        db, "evt_example", json.dumps(data).encode(), data
    )
    assert result == "ignored"
    assert db.record.error_code == code
    assert owner.subscription_status == "trialing"


async def test_late_webhook_cannot_undo_newer_state(monkeypatch):
    owner = merchant(subscription_status="active", razorpay_subscription_id="sub_example")
    db = WebhookDatabase(
        owner, previous=(NOW + timedelta(seconds=10), "subscription.activated")
    )
    monkeypatch.setattr(billing_webhooks, "get_settings", lambda: SimpleNamespace(
        razorpay_plan_id="plan_example", billing_plan_amount_paise=149900,
    ))
    data = webhook_data("subscription.pending")
    result = await billing_webhooks.process_verified_event(
        db, "evt_example", json.dumps(data).encode(), data
    )
    assert result == "ignored"
    assert db.record.error_code == "stale_event"
    assert owner.subscription_status == "active"


async def test_subscribe_reuses_existing_subscription_without_network(monkeypatch):
    owner = merchant(razorpay_subscription_id="sub_existing")
    settings = SimpleNamespace(razorpay_key_id="public", razorpay_plan_id="plan_example")

    class Database:
        async def scalar(self, _statement):
            return owner

    async def read_existing(_settings, method, path, _payload=None):
        assert method == "GET"
        assert path == "/subscriptions/sub_existing"
        return {"status": "authenticated"}

    monkeypatch.setattr(billing, "get_settings", lambda: settings)
    monkeypatch.setattr(billing, "require_billing_config", lambda _settings: None)
    monkeypatch.setattr(billing, "razorpay_request", read_existing)
    result = await billing.subscribe(owner, Database(), lambda: NOW, Response())
    assert result.subscription_id == "sub_existing"
    assert result.key_id == "public"


async def test_webhook_signature_gate_and_event_deduplication(monkeypatch):
    secret = secrets.token_hex(32)
    settings = SimpleNamespace(razorpay_webhook_secret=SecretStr(secret))
    monkeypatch.setattr(billing_webhooks, "get_settings", lambda: settings)

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Database:
        def __init__(self):
            self.seen = set()
            self.record = SimpleNamespace()

        async def execute(self, statement):
            event_id = statement.compile().params["event_id"]
            if event_id in self.seen:
                return Result(None)
            self.seen.add(event_id)
            return Result(event_id)

        async def get(self, _model, _key):
            return self.record

        async def commit(self):
            pass

    db = Database()
    app.dependency_overrides[get_db] = lambda: db
    body = json.dumps(
        {"event": "subscription.unknown", "created_at": int(NOW.timestamp())}
    ).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"X-Razorpay-Signature": signature, "x-razorpay-event-id": "evt_example"}
            invalid = await client.post("/api/v1/webhooks/razorpay", content=body,
                                        headers={**headers, "X-Razorpay-Signature": "bad"})
            tampered = await client.post("/api/v1/webhooks/razorpay", content=body + b" ",
                                         headers=headers)
            first = await client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)
            duplicate = await client.post(
                "/api/v1/webhooks/razorpay", content=body, headers=headers
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert invalid.status_code == 400
    assert tampered.status_code == 400
    assert first.status_code == 200 and first.json() == {"status": "ignored"}
    assert duplicate.status_code == 200 and duplicate.json() == {"status": "duplicate"}
    assert len(db.seen) == 1


async def test_locked_merchant_routes_and_customer_manage_link(monkeypatch):
    owner = merchant(trial_ends_at=NOW - timedelta(days=1))

    class Database:
        def begin(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def scalar(self, _statement):
            return owner

    async def fail_booking(*_args, **_kwargs):
        pytest.fail("Booking logic must not run for a locked merchant")

    monkeypatch.setattr(confirmed_bookings, "confirm_booking_without_payment", fail_booking)
    app.dependency_overrides[get_db] = lambda: Database()
    app.dependency_overrides[get_current_merchant] = lambda: owner
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            services = await client.get("/api/v1/services")
            booking = await client.post("/api/v1/bookings/initiate", json={
                "service_id": str(uuid4()), "customer_name": "A Customer",
                "customer_phone": "9876543210", "booking_date": "2030-01-02", "start_time": "10:00",
            })
            manage = await client.get("/api/v1/manage/invalid")
    finally:
        for dependency in (get_db, get_current_merchant, get_clock):
            app.dependency_overrides.pop(dependency, None)
    assert services.status_code == 403
    assert services.json()["error"]["code"] == "subscription_required"
    assert booking.status_code == 403
    assert booking.json()["error"]["code"] == "subscription_required"
    assert manage.status_code == 404  # Customer management is not subscription gated.


async def test_lock_dependency_uses_subscription_required_code():
    with pytest.raises(AppError) as caught:
        await require_billing_access(merchant(trial_ends_at=NOW), lambda: NOW)
    assert caught.value.code == "subscription_required"


def test_billing_migration_is_additive_and_reversible_offline(monkeypatch):
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/b7e3f29c41aa_add_merchant_subscription_billing.py"
    )
    spec = importlib.util.spec_from_file_location("billing_migration", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(migration)
    assert migration.down_revision == "c6b2e4d9108a"
    config = Config()
    config.set_main_option("script_location", str(path.parents[1]))
    assert ScriptDirectory.from_config(config).get_heads() == ["b7e3f29c41aa"]
    monkeypatch.setenv("BILLING_TRIAL_DAYS", "30")

    def render(operation):
        output = StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
        with Operations.context(context):
            operation()
        return output.getvalue()

    upgrade = render(migration.upgrade)
    downgrade = render(migration.downgrade)
    assert "CREATE TABLE billing_payments" in upgrade
    assert "CREATE TABLE billing_webhook_events" in upgrade
    assert "ALTER TABLE merchants ADD COLUMN trial_ends_at" in upgrade
    assert "UPDATE merchants SET trial_ends_at" in upgrade
    assert "DROP TABLE" not in upgrade
    assert "bookings" not in upgrade
    assert "DROP TABLE billing_payments" in downgrade
    assert "DROP TABLE billing_webhook_events" in downgrade
    assert "DROP TABLE merchants" not in downgrade
