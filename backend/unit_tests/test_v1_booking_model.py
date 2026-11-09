"""Offline checks for the additive V1 booking model migration and policy contract."""

import hashlib
import importlib.util
from datetime import UTC, date, datetime, time
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.v1 import confirmed_bookings
from app.core.database import get_db
from app.main import app as default_app
from app.models import Booking, Service
from app.models.enums import BookingStatus, PaymentStatus
from app.schemas.api import ServiceCreate, ServiceUpdate
from app.v1_main import app as v1_app

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/c6b2e4d9108a_add_v1_service_policies_and_management_token.py"
)


def test_service_policies_are_opt_in_and_validated():
    service = ServiceCreate(
        title="Yoga",
        category="Classes",
        booking_mode="BATCH",
        price="500.00",
        max_capacity=12,
    )
    assert service.reschedule_cutoff_hours is None
    assert service.allow_cancellations is False
    assert service.cancel_cutoff_hours == 0

    configured = ServiceUpdate(
        reschedule_cutoff_hours=12, allow_cancellations=True, cancel_cutoff_hours=24
    )
    assert configured.model_dump(exclude_unset=True) == {
        "reschedule_cutoff_hours": 12,
        "allow_cancellations": True,
        "cancel_cutoff_hours": 24,
    }
    for field in ("reschedule_cutoff_hours", "cancel_cutoff_hours"):
        with pytest.raises(ValidationError):
            ServiceUpdate.model_validate({field: -1})


def test_many_services_can_belong_to_one_merchant_and_tokens_are_unique():
    assert Service.__table__.c.merchant_id.unique is not True
    assert Service.__table__.c.reschedule_cutoff_hours.nullable
    assert not Service.__table__.c.allow_cancellations.nullable
    assert Booking.__table__.c.management_token_hash.nullable
    assert any(
        constraint.name == "uq_bookings_management_token_hash"
        for constraint in Booking.__table__.constraints
    )


def test_v1_app_exposes_booking_submission_without_razorpay_routes():
    assert default_app is v1_app
    paths = v1_app.openapi()["paths"]
    assert "post" in paths["/api/v1/bookings/initiate"]
    assert not any("/payment" in path for path in paths)
    assert "post" in paths["/api/v1/webhooks/razorpay"]
    assert "get" in paths["/api/v1/storefront/{slug}"]


async def test_v1_booking_confirms_atomically_without_recording_payment(monkeypatch):
    from app.services import booking_service

    customer = SimpleNamespace(total_bookings_count=0)
    booking = SimpleNamespace(
        customer_id=uuid4(),
        booking_status=BookingStatus.PENDING_PAYMENT,
        payment_status=PaymentStatus.PENDING,
        hold_expires_at=datetime.now(UTC),
        amount_to_pay=Decimal("250.00"),
    )

    async def hold(*args, **kwargs):
        return booking

    class Database:
        async def get(self, model, key):
            assert model is not None and key == booking.customer_id
            return customer

    monkeypatch.setattr(booking_service, "initiate_booking", hold)
    result = await booking_service.confirm_booking_without_payment(Database(), object())
    assert result is booking
    assert booking.booking_status is BookingStatus.CONFIRMED
    assert booking.payment_status is PaymentStatus.PENDING
    assert booking.hold_expires_at is None
    assert booking.amount_to_pay == Decimal("0.00")
    assert customer.total_bookings_count == 1


async def test_v1_http_response_issues_a_hashed_management_token(monkeypatch):
    booking = SimpleNamespace(
        booking_reference="TI-20300107-TESTTOKEN1",
        booking_status=BookingStatus.CONFIRMED,
        payment_status=PaymentStatus.PENDING,
        booking_date=date(2030, 1, 7),
        start_time=time(10),
        end_time=time(11),
        staff_member_id=None,
        batch_schedule_id=None,
        amount_to_pay=Decimal("0.00"),
        hold_expires_at=None,
        management_token_hash=None,
        service_id=uuid4(),
        merchant_id=uuid4(),
        customer_id=uuid4(),
    )

    class Database:
        def begin(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    async def override_db():
        yield Database()

    async def confirm(*args, **kwargs):
        return booking

    async def no_notification_details(*args, **kwargs):
        return None

    async def allow_booking(*args, **kwargs):
        return None

    monkeypatch.setattr(confirmed_bookings, "confirm_booking_without_payment", confirm)
    monkeypatch.setattr(confirmed_bookings, "get_notification_details", no_notification_details)
    monkeypatch.setattr(confirmed_bookings, "require_booking_access", allow_booking)
    v1_app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=v1_app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/bookings/initiate",
                json={
                    "service_id": str(uuid4()),
                    "customer_name": "A Customer",
                    "customer_phone": "9876543210",
                    "booking_date": "2030-01-07",
                    "start_time": "10:00",
                },
            )
    finally:
        v1_app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["booking_status"] == "CONFIRMED"
    assert body["amount_to_pay"] == "0.00"
    assert body["hold_expires_at"] is None
    assert body["public_booking_token"] is None
    token = body["management_token"]
    assert len(token) >= 40
    assert booking.management_token_hash == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert token != booking.management_token_hash


def test_v1_migration_is_additive_and_reversible_without_database_access():
    spec = importlib.util.spec_from_file_location("v1_booking_model_migration", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(migration)
    assert migration.down_revision == "a7d8c9012f34"

    config = Config()
    config.set_main_option("script_location", str(MIGRATION.parents[1]))
    assert ScriptDirectory.from_config(config).get_heads() == ["b7e3f29c41aa"]

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
    assert "ALTER TABLE services ADD COLUMN reschedule_cutoff_hours" in upgrade
    assert "ALTER TABLE services ADD COLUMN allow_cancellations" in upgrade
    assert "ALTER TABLE services ADD COLUMN cancel_cutoff_hours" in upgrade
    assert "ALTER TABLE bookings ADD COLUMN management_token_hash" in upgrade
    assert "uq_bookings_management_token_hash" in upgrade
    assert "DROP TABLE" not in upgrade
    assert "waitlist_entries" not in upgrade
    assert "DROP COLUMN" not in upgrade
    assert "DROP COLUMN management_token_hash" in downgrade
    assert "DROP COLUMN reschedule_cutoff_hours" in downgrade
    assert "waitlist_entries" not in downgrade
