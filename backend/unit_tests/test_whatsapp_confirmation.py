"""Database-free tests for the V1 WhatsApp confirmation handoff."""

import json
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.v1 import confirmed_bookings
from app.core.database import get_db
from app.models.enums import BookingStatus, PaymentStatus
from app.services import whatsapp_service
from app.v1_main import app


@pytest.mark.parametrize(
    ("function_name", "template_name"),
    [
        ("send_booking_confirmation", "booking_confirmation_v1"),
        ("send_reschedule_confirmation", "reschedule_confirmation_v1"),
    ],
)
async def test_meta_template_payload_and_authorization(monkeypatch, function_name, template_name):
    captured = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "test-message-id"}]})

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        whatsapp_service.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(
        whatsapp_service,
        "get_settings",
        lambda: SimpleNamespace(
            whatsapp_phone_number_id="123456789",
            whatsapp_api_token=SecretStr("test-only-token"),
            whatsapp_api_version="v26.0",
        ),
    )

    await getattr(whatsapp_service, function_name)(
        "+919876543210",
        "Yoga",
        "Example Studio",
        "07 Jan 2030, 10:00 AM",
        "https://example.test/manage/token",
    )

    assert captured["url"] == "https://graph.facebook.com/v26.0/123456789/messages"
    assert captured["authorization"] == "Bearer test-only-token"
    assert captured["payload"]["to"] == "919876543210"
    template = captured["payload"]["template"]
    assert template["name"] == template_name
    assert template["language"] == {"code": "en"}
    assert [item["text"] for item in template["components"][0]["parameters"]] == [
        "Yoga",
        "Example Studio",
        "07 Jan 2030, 10:00 AM",
        "https://example.test/manage/token",
    ]


@pytest.mark.parametrize(
    "function_name", ["send_booking_confirmation", "send_reschedule_confirmation"]
)
async def test_missing_meta_credentials_skips_network(monkeypatch, function_name):
    monkeypatch.setattr(
        whatsapp_service,
        "get_settings",
        lambda: SimpleNamespace(whatsapp_phone_number_id=None, whatsapp_api_token=None),
    )

    def fail_if_client_created(**kwargs):
        raise AssertionError("An HTTP client must not be created without credentials")

    monkeypatch.setattr(whatsapp_service.httpx, "AsyncClient", fail_if_client_created)
    await getattr(whatsapp_service, function_name)(
        "+919876543210",
        "Yoga",
        "Example Studio",
        "07 Jan 2030, 10:00 AM",
        "https://example.test/manage/token",
    )


async def test_notification_details_query_is_tenant_scoped():
    service_id, merchant_id, customer_id = uuid4(), uuid4(), uuid4()

    class Result:
        def one_or_none(self):
            return ("Yoga", "Example Studio", "+919876543210")

    class Database:
        async def execute(self, statement):
            sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
            assert service_id.hex in sql
            assert merchant_id.hex in sql
            assert customer_id.hex in sql
            assert "JOIN merchants" in sql
            assert "JOIN customers" in sql
            assert "customers.merchant_id = merchants.id" in sql
            return Result()

    assert await confirmed_bookings.get_notification_details(
        Database(), service_id, merchant_id, customer_id
    ) == ("Yoga", "Example Studio", "+919876543210")


async def test_whatsapp_task_runs_only_after_booking_commit(monkeypatch):
    events = []
    booking = SimpleNamespace(
        booking_reference="TI-20300107-WHATSAPP",
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
            events.append("begin")
            return self

        async def __aexit__(self, exc_type, *_):
            events.append("commit" if exc_type is None else "rollback")
            return False

    async def override_db():
        yield Database()

    async def confirm(*args, **kwargs):
        events.append("confirm")
        return booking

    async def details(db, service_id, merchant_id, customer_id):
        assert events[-1] == "commit"
        assert (service_id, merchant_id, customer_id) == (
            booking.service_id,
            booking.merchant_id,
            booking.customer_id,
        )
        events.append("details")
        return ("Yoga", "Example Studio", "+919876543210")

    async def send(*args):
        events.append("send")
        assert args[:4] == ("+919876543210", "Yoga", "Example Studio", "07 Jan 2030, 10:00 AM")
        assert args[4].startswith("https://typein.co/manage/")

    monkeypatch.setattr(confirmed_bookings, "confirm_booking_without_payment", confirm)
    monkeypatch.setattr(confirmed_bookings, "get_notification_details", details)
    monkeypatch.setattr(confirmed_bookings, "send_booking_confirmation", send)
    async def allow_booking(*_args, **_kwargs):
        return None

    monkeypatch.setattr(confirmed_bookings, "require_booking_access", allow_booking)
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/bookings/initiate",
                json={
                    "service_id": str(booking.service_id),
                    "customer_name": "A Customer",
                    "customer_phone": "9876543210",
                    "booking_date": "2030-01-07",
                    "start_time": "10:00",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 201
    assert events == ["begin", "confirm", "commit", "details", "send"]
