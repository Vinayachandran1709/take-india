"""Database-free contract checks for the merchant agenda."""

from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_clock, get_current_merchant, require_billing_access
from app.core.database import get_db
from app.models.enums import BookingStatus
from app.v1_main import app


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeDatabase:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeRows(self.rows)


async def test_agenda_requires_merchant_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/merchants/me/agenda")
    assert response.status_code == 401


async def test_agenda_returns_tenant_scoped_confirmed_bookings():
    merchant = SimpleNamespace(id=uuid4(), timezone="Asia/Kolkata")
    booking = SimpleNamespace(
        booking_reference="TI-20300106-AGENDA01",
        booking_date=date(2030, 1, 6),
        start_time=time(10),
        end_time=time(11),
        booking_status=BookingStatus.CONFIRMED,
    )
    db = FakeDatabase([(booking, "Yoga", "Customer", "+919876543210")])
    app.dependency_overrides[get_current_merchant] = lambda: merchant
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_clock] = lambda: lambda: datetime(2030, 1, 5, 19, 0, tzinfo=UTC)
    app.dependency_overrides[require_billing_access] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/merchants/me/agenda")
    finally:
        for dependency in (get_current_merchant, get_db, get_clock, require_billing_access):
            app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "today": "2030-01-06",
        "tomorrow": "2030-01-07",
        "timezone": "Asia/Kolkata",
        "bookings": [
            {
                "booking_reference": booking.booking_reference,
                "booking_date": "2030-01-06",
                "start_time": "10:00:00",
                "end_time": "11:00:00",
                "booking_status": "CONFIRMED",
                "service_title": "Yoga",
                "customer_name": "Customer",
                "customer_phone": "+919876543210",
            }
        ],
    }
    sql = str(db.statement)
    assert "bookings.merchant_id" in sql
    assert "bookings.booking_date BETWEEN" in sql
    assert "bookings.booking_status" in sql
    assert "JOIN services" in sql and "JOIN customers" in sql
    assert "services.merchant_id = bookings.merchant_id" in sql
    assert "customers.merchant_id = bookings.merchant_id" in sql
