from datetime import timedelta

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking
from scripts.seed import seed_data
from tests.conftest import FIXED_NOW


@pytest.mark.asyncio
async def test_seeded_public_availability_and_unpaid_holds(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_http(*args, **kwargs):
        pytest.fail("Public hold attempted outbound HTTP/payment request")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_http)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden_http)
    await seed_data(db)
    for slug, mode, title in (
        ("glow-salon-spa", "APPOINTMENT", "Signature Hair & Spa"),
        ("beatz-dance-studio", "BATCH", "Evening Dance Batch"),
        ("sweet-crumbs", "CUSTOM_ORDER", "Custom Celebration Cake"),
    ):
        response = await client.get(f"/api/v1/storefront/{slug}")
        assert response.status_code == 200
        offering = response.json()["services"][0]
        assert (offering["booking_mode"], offering["title"]) == (mode, title)
        params = {"service_id": offering["id"], "date": "2030-01-07"}
        path = f"/api/v1/storefront/{slug}/available-slots"
        available = await client.get(path, params=params)
        assert available.status_code == 200
        slot = available.json()["available_slots"][0]
        assert slot["available"]
        payload = {
            "service_id": offering["id"],
            "booking_date": "2030-01-07",
            "customer_name": "Acceptance Customer",
            "customer_phone": "9876543219",
            "start_time": slot["start_time"],
            "custom_field_responses": {},
        }
        if mode == "APPOINTMENT":
            payload["staff_member_id"] = slot["available_staff"][0]["id"]
        elif mode == "BATCH":
            payload.pop("start_time")
            payload["batch_schedule_id"] = slot["batch_schedule_id"]
        else:
            assert len(offering["custom_fields"]) == 3
            payload["end_time"] = "10:00"
            payload["custom_field_responses"] = {"Flavor": "Vanilla", "Eggless": False}
        held = await client.post("/api/v1/bookings/initiate", json=payload)
        assert held.status_code == 201, held.text
        assert held.json()["booking_status"] == "PENDING_PAYMENT"
        assert held.json()["payment_status"] == "PENDING"
        booking = await db.scalar(
            select(Booking).where(Booking.booking_reference == held.json()["booking_reference"])
        )
        assert booking.razorpay_order_id is None
        assert booking.razorpay_payment_id is None
        if mode == "CUSTOM_ORDER":
            continue
        active = (await client.get(path, params=params)).json()["available_slots"][0]
        if mode == "APPOINTMENT":
            assert payload["staff_member_id"] not in {
                member["id"] for member in active["available_staff"]
            }
            assert (await client.post("/api/v1/bookings/initiate", json=payload)).status_code == 409
        else:
            assert active["remaining_capacity"] == slot["remaining_capacity"] - 1
        booking.hold_expires_at = FIXED_NOW - timedelta(seconds=1)
        await db.commit()
        expired = (await client.get(path, params=params)).json()["available_slots"][0]
        assert expired == slot
        assert (await client.post("/api/v1/bookings/initiate", json=payload)).status_code == 201
