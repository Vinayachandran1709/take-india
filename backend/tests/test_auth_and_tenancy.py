from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, Customer, OperatingHour, ServiceStaff
from app.models.enums import BookingStatus, PaymentStatus
from tests.helpers import merchant, service, staff


@pytest.mark.asyncio
async def test_health_signup_login_me_and_wrong_password(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Glow Test",
            "slug": "glow-test",
            "business_type": "SALON",
            "owner_name": "Owner",
            "phone_number": "9876543210",
            "email": "OWNER@EXAMPLE.COM",
            "password": "password123",
        },
    )
    assert signup.status_code == 201, signup.text
    body = signup.json()
    assert body["merchant"]["phone_number"] == "+919876543210"
    token = body["access_token"]
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    wrong = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "incorrect"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    invalid_phone = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Bad Phone",
            "slug": "bad-phone",
            "business_type": "SALON",
            "owner_name": "Owner",
            "phone_number": "123",
            "email": "bad-phone@example.com",
            "password": "password123",
        },
    )
    assert invalid_phone.status_code == 400
    assert invalid_phone.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_cross_tenant_service_is_hidden(client: AsyncClient) -> None:
    async def signup(slug: str, email: str) -> str:
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "business_name": slug,
                "slug": slug,
                "business_type": "SALON",
                "owner_name": "Owner",
                "phone_number": "+919876543210",
                "email": email,
                "password": "password123",
            },
        )
        return response.json()["access_token"]

    owner = await signup("owner-one", "one@example.com")
    outsider = await signup("owner-two", "two@example.com")
    created = await client.post(
        "/api/v1/services",
        headers={"Authorization": f"Bearer {owner}"},
        json={
            "title": "Haircut",
            "category": "Salon",
            "booking_mode": "APPOINTMENT",
            "price": "500.00",
            "advance_token_amount": "100.00",
            "duration_minutes": 30,
        },
    )
    assert created.status_code == 201, created.text
    service_id = created.json()["id"]
    headers = {"Authorization": f"Bearer {outsider}"}
    for response in (
        await client.get(f"/api/v1/services/{service_id}", headers=headers),
        await client.patch(
            f"/api/v1/services/{service_id}", headers=headers, json={"title": "Nope"}
        ),
        await client.delete(f"/api/v1/services/{service_id}", headers=headers),
    ):
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_database_rejects_cross_tenant_service_staff(db: AsyncSession) -> None:
    first = await merchant(db, slug="first", email="first@example.com")
    second = await merchant(db, slug="second", email="second@example.com")
    owned_service = await service(db, first.id)
    other_staff = await staff(db, second.id, "Other")
    await db.commit()
    db.add(
        ServiceStaff(
            merchant_id=first.id,
            service_id=owned_service.id,
            staff_member_id=other_staff.id,
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()


@pytest.mark.asyncio
async def test_nested_resources_are_tenant_scoped_and_soft_delete_is_repeatable(
    client: AsyncClient,
) -> None:
    async def create_account(slug: str, email: str) -> str:
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "business_name": slug,
                "slug": slug,
                "business_type": "ACADEMY",
                "owner_name": "Owner",
                "phone_number": "9876543210",
                "email": email,
                "password": "password123",
            },
        )
        return response.json()["access_token"]

    owner_token = await create_account("config-owner", "config-owner@example.com")
    outsider_token = await create_account("config-outsider", "config-outsider@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}
    member = await client.post("/api/v1/staff", headers=owner_headers, json={"name": "Asha"})
    staff_id = member.json()["id"]
    created = await client.post(
        "/api/v1/services",
        headers=owner_headers,
        json={
            "title": "Batch class",
            "category": "Dance",
            "booking_mode": "BATCH",
            "price": "1000.00",
            "advance_token_amount": "100.00",
            "max_capacity": 10,
        },
    )
    service_id = created.json()["id"]
    field = await client.post(
        f"/api/v1/services/{service_id}/custom-fields",
        headers=owner_headers,
        json={"field_label": "Level", "field_type": "TEXT", "is_required": False},
    )
    field_id = field.json()["id"]
    schedule = await client.post(
        f"/api/v1/services/{service_id}/batch-schedules",
        headers=owner_headers,
        json={
            "day_of_week": 1,
            "start_time": "19:00",
            "end_time": "20:00",
            "max_capacity": 10,
        },
    )
    schedule_id = schedule.json()["id"]
    assert field.status_code == 201
    assert schedule.status_code == 201

    attempts = (
        await client.get(
            f"/api/v1/services/{service_id}/custom-fields", headers=outsider_headers
        ),
        await client.patch(
            f"/api/v1/services/{service_id}/custom-fields/{field_id}",
            headers=outsider_headers,
            json={"field_label": "Nope"},
        ),
        await client.delete(
            f"/api/v1/services/{service_id}/custom-fields/{field_id}",
            headers=outsider_headers,
        ),
        await client.get(
            f"/api/v1/services/{service_id}/batch-schedules", headers=outsider_headers
        ),
        await client.patch(
            f"/api/v1/services/{service_id}/batch-schedules/{schedule_id}",
            headers=outsider_headers,
            json={"max_capacity": 2},
        ),
        await client.delete(
            f"/api/v1/services/{service_id}/batch-schedules/{schedule_id}",
            headers=outsider_headers,
        ),
        await client.patch(
            f"/api/v1/staff/{staff_id}", headers=outsider_headers, json={"name": "Nope"}
        ),
        await client.delete(f"/api/v1/staff/{staff_id}", headers=outsider_headers),
    )
    assert all(response.status_code == 404 for response in attempts)

    for path in (
        f"/api/v1/staff/{staff_id}",
        f"/api/v1/services/{service_id}/batch-schedules/{schedule_id}",
        f"/api/v1/services/{service_id}",
    ):
        assert (await client.delete(path, headers=owner_headers)).status_code == 204
        assert (await client.delete(path, headers=owner_headers)).status_code == 204


@pytest.mark.asyncio
async def test_operating_hours_put_upserts(client: AsyncClient, db: AsyncSession) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Hours",
            "slug": "hours",
            "business_type": "SALON",
            "owner_name": "Owner",
            "phone_number": "9876543210",
            "email": "hours@example.com",
            "password": "password123",
        },
    )
    merchant_id = signup.json()["merchant"]["id"]
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    for close_time in ("17:00", "18:00"):
        response = await client.put(
            "/api/v1/operating-hours",
            headers=headers,
            json={
                "days": [
                    {
                        "day_of_week": 1,
                        "open_time": "10:00",
                        "close_time": close_time,
                        "is_closed": False,
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
    count = await db.scalar(
        select(func.count(OperatingHour.id)).where(OperatingHour.merchant_id == merchant_id)
    )
    row = await db.scalar(
        select(OperatingHour).where(OperatingHour.merchant_id == merchant_id)
    )
    assert count == 1
    assert str(row.close_time) == "18:00:00"


@pytest.mark.asyncio
async def test_database_rejects_cross_tenant_booking_relationship(db: AsyncSession) -> None:
    first = await merchant(db, slug="booking-first", email="booking-first@example.com")
    second = await merchant(db, slug="booking-second", email="booking-second@example.com")
    owned_service = await service(db, first.id)
    foreign_customer = Customer(
        merchant_id=second.id,
        full_name="Wrong tenant",
        phone_number="+919876543219",
        total_bookings_count=0,
    )
    db.add(foreign_customer)
    await db.commit()
    db.add(
        Booking(
            booking_reference="TI-20300107-TENANT0001",
            merchant_id=first.id,
            service_id=owned_service.id,
            customer_id=foreign_customer.id,
            booking_date=date(2030, 1, 7),
            start_time=time(10),
            end_time=time(11),
            custom_field_responses={},
            total_amount=Decimal("1500.00"),
            amount_to_pay=Decimal("300.00"),
            booking_status=BookingStatus.PENDING_PAYMENT,
            payment_status=PaymentStatus.PENDING,
            hold_expires_at=datetime(2030, 1, 6, 0, 10, tzinfo=UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
