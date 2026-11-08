"""Database-free checks for passwordless booking management."""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_clock
from app.api.v1 import manage as manage_module
from app.api.v1.manage import _permissions
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.management_token import new_management_token
from app.models.enums import BookingMode, BookingStatus
from app.v1_main import app

NOW = datetime(2030, 1, 6, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def prevent_external_messages(monkeypatch):
    async def stub(*args):
        return None

    monkeypatch.setattr(manage_module, "send_reschedule_confirmation", stub)


class FakeResult:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class FakeDatabase:
    def __init__(self, booking, service, merchant, *, schedule=None, occupied_count=0):
        self.booking = booking
        self.service = service
        self.merchant = merchant
        self.schedule = schedule
        self.occupied_count = occupied_count
        self.hours = SimpleNamespace(is_closed=False, open_time=time(9), close_time=time(18))
        self.customer_phone = "+919876543210"
        self.statements = []
        self.commits = 0

    async def execute(self, statement):
        self.statements.append(statement)
        if self.booking is None:
            return FakeResult(None)
        return FakeResult((self.booking, self.service, self.merchant))

    async def scalar(self, statement):
        self.statements.append(statement)
        query = str(statement)
        if "count(" in query:
            return self.occupied_count
        if "operating_hours" in query:
            return self.hours
        if "customers.phone_number" in query:
            return self.customer_phone
        return self.schedule

    async def commit(self):
        self.commits += 1


@asynccontextmanager
async def client_for(db, now=NOW):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_clock] = lambda: lambda: now
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_clock, None)


def booking_data(*, mode=BookingMode.APPOINTMENT):
    token, digest = new_management_token()
    merchant = SimpleNamespace(
        id=uuid4(), slug="example-studio", business_name="Example Studio", timezone="Asia/Kolkata"
    )
    service = SimpleNamespace(
        id=uuid4(),
        title="Yoga",
        booking_mode=mode,
        allow_cancellations=True,
        cancel_cutoff_hours=12,
        reschedule_cutoff_hours=12,
        duration_minutes=60,
        prep_lead_time_hours=None,
    )
    booking = SimpleNamespace(
        id=uuid4(),
        customer_id=uuid4(),
        service_id=service.id,
        merchant_id=merchant.id,
        booking_reference="TI-20300107-MANAGE001",
        booking_date=date(2030, 1, 7),
        start_time=time(10),
        end_time=time(11),
        booking_status=BookingStatus.CONFIRMED,
        management_token_hash=digest,
        batch_schedule_id=None,
        staff_member_id=None,
    )
    return token, booking, service, merchant


async def test_manage_get_exposes_only_booking_details_and_policy_flags():
    token, booking, service, merchant = booking_data()
    db = FakeDatabase(booking, service, merchant)
    async with client_for(db) as client:
        response = await client.get(f"/api/v1/manage/{token}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.json() == {
        "booking_reference": booking.booking_reference,
        "service_id": str(service.id),
        "merchant_id": str(merchant.id),
        "merchant_slug": merchant.slug,
        "booking_mode": "APPOINTMENT",
        "booking_date": "2030-01-07",
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "booking_status": "CONFIRMED",
        "service_title": "Yoga",
        "business_name": "Example Studio",
        "timezone": "Asia/Kolkata",
        "can_cancel": True,
        "can_reschedule": True,
    }
    assert token not in response.text
    statement = db.statements[0]
    assert booking.management_token_hash in statement.compile().params.values()
    sql = str(statement)
    assert "JOIN services" in sql and "JOIN merchants" in sql
    assert "services.merchant_id = bookings.merchant_id" in sql


async def test_invalid_and_unknown_tokens_return_404():
    token, booking, service, merchant = booking_data()
    db = FakeDatabase(booking, service, merchant)
    async with client_for(db) as client:
        malformed = await client.get("/api/v1/manage/not-a-token")
    assert malformed.status_code == 404
    assert not db.statements

    db.booking = None
    async with client_for(db) as client:
        unknown = await client.get(f"/api/v1/manage/{token}")
    assert unknown.status_code == 404


def test_cutoffs_are_strict_and_use_merchant_local_time():
    _, booking, service, merchant = booking_data()
    appointment_utc = datetime(2030, 1, 7, 4, 30, tzinfo=UTC)
    assert _permissions(booking, service, merchant, appointment_utc - timedelta(hours=12)) == (
        False,
        False,
    )
    assert _permissions(
        booking, service, merchant, appointment_utc - timedelta(hours=12, seconds=1)
    ) == (True, True)
    booking.booking_status = BookingStatus.CANCELLED
    assert _permissions(booking, service, merchant, NOW) == (False, False)


async def test_cancel_locks_booking_and_commits_only_when_permitted():
    token, booking, service, merchant = booking_data()
    db = FakeDatabase(booking, service, merchant)
    async with client_for(db) as client:
        response = await client.post(f"/api/v1/manage/{token}/cancel")
    assert response.status_code == 200
    assert response.json() == {"message": "Booking cancelled"}
    assert booking.booking_status == BookingStatus.CANCELLED
    assert db.commits == 1
    assert db.statements[0]._for_update_arg is not None

    async with client_for(db) as client:
        repeated = await client.post(f"/api/v1/manage/{token}/cancel")
    assert repeated.status_code == 400
    assert db.commits == 1


async def test_reschedule_updates_end_time_and_rejects_cutoff(monkeypatch):
    token, booking, service, merchant = booking_data()
    db = FakeDatabase(booking, service, merchant)
    sent = []

    async def available_resource(*args, **kwargs):
        assert kwargs["exclude_booking_id"] == booking.id
        return None

    async def send(*args):
        assert db.commits == 1
        sent.append(args)

    monkeypatch.setattr(manage_module, "appointment_resource", available_resource)
    monkeypatch.setattr(manage_module, "send_reschedule_confirmation", send)
    async with client_for(db) as client:
        response = await client.post(
            f"/api/v1/manage/{token}/reschedule",
            json={"new_booking_date": "2030-01-08", "new_start_time": "11:00"},
        )
    assert response.status_code == 200
    assert response.json() == {"message": "Booking rescheduled"}
    assert (booking.booking_date, booking.start_time, booking.end_time) == (
        date(2030, 1, 8),
        time(11),
        time(12),
    )
    assert db.commits == 1
    assert db.statements[0]._for_update_arg is not None
    assert sent == [
        (
            "+919876543210",
            "Yoga",
            "Example Studio",
            "08 Jan 2030, 11:00 AM",
            f"https://typein.co/manage/{token}",
        )
    ]

    service.reschedule_cutoff_hours = None
    async with client_for(db) as client:
        denied = await client.post(
            f"/api/v1/manage/{token}/reschedule",
            json={"new_booking_date": "2030-01-09", "new_start_time": "11:00"},
        )
    assert denied.status_code == 400
    assert db.commits == 1
    assert len(sent) == 1


async def test_batch_reschedule_reassigns_matching_schedule():
    token, booking, service, merchant = booking_data(mode=BookingMode.BATCH)
    schedule = SimpleNamespace(id=uuid4(), end_time=time(12), max_capacity=2)
    db = FakeDatabase(booking, service, merchant, schedule=schedule)
    async with client_for(db) as client:
        response = await client.post(
            f"/api/v1/manage/{token}/reschedule",
            json={"new_booking_date": "2030-01-08", "new_start_time": "11:00"},
        )
    assert response.status_code == 200
    assert booking.batch_schedule_id == schedule.id
    assert booking.end_time == schedule.end_time
    assert db.commits == 1


async def test_batch_reschedule_rejects_full_class_without_commit():
    token, booking, service, merchant = booking_data(mode=BookingMode.BATCH)
    schedule = SimpleNamespace(id=uuid4(), end_time=time(12), max_capacity=2)
    db = FakeDatabase(booking, service, merchant, schedule=schedule, occupied_count=2)
    async with client_for(db) as client:
        response = await client.post(
            f"/api/v1/manage/{token}/reschedule",
            json={"new_booking_date": "2030-01-08", "new_start_time": "11:00"},
        )
    assert response.status_code == 409
    assert db.commits == 0


async def test_appointment_reschedule_rejects_occupied_resource(monkeypatch):
    token, booking, service, merchant = booking_data()
    db = FakeDatabase(booking, service, merchant)

    async def occupied_resource(*args, **kwargs):
        raise AppError("SLOT_UNAVAILABLE", "This appointment time is unavailable", 409)

    monkeypatch.setattr(manage_module, "appointment_resource", occupied_resource)
    async with client_for(db) as client:
        response = await client.post(
            f"/api/v1/manage/{token}/reschedule",
            json={"new_booking_date": "2030-01-08", "new_start_time": "11:00"},
        )
    assert response.status_code == 409
    assert db.commits == 0
    assert booking.booking_date == date(2030, 1, 7)


async def test_reschedule_rejects_past_and_offset_times_without_commit():
    token, booking, service, merchant = booking_data()
    db = FakeDatabase(booking, service, merchant)
    async with client_for(db) as client:
        past = await client.post(
            f"/api/v1/manage/{token}/reschedule",
            json={"new_booking_date": "2030-01-05", "new_start_time": "11:00"},
        )
        offset = await client.post(
            f"/api/v1/manage/{token}/reschedule",
            json={"new_booking_date": "2030-01-08", "new_start_time": "11:00+05:30"},
        )
    assert past.status_code == 400
    assert offset.status_code == 400
    assert db.commits == 0
