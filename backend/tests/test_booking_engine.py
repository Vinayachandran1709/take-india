import asyncio
from datetime import UTC, date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    BatchSchedule,
    Booking,
    Customer,
    OperatingHour,
    ServiceCustomField,
)
from app.models.enums import BookingMode, BookingStatus, CustomFieldType, PaymentStatus
from app.schemas.api import BookingInitiateRequest
from app.services.booking_service import initiate_booking
from tests.conftest import FIXED_NOW
from tests.helpers import assign, merchant, monday_hours, service, staff

BOOKING_DATE = date(2030, 1, 7)


def booking_payload(service_id: str, **changes) -> dict:
    payload = {
        "service_id": service_id,
        "customer_name": "A Customer",
        "customer_phone": "9876543211",
        "booking_date": BOOKING_DATE.isoformat(),
        "start_time": "10:00",
        "custom_field_responses": {},
    }
    payload.update(changes)
    return payload


@pytest.mark.asyncio
async def test_appointment_availability_and_server_derived_hold(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(db, owner.id)
    member = await staff(db, owner.id, "Asha")
    db.add_all([assign(offering, member), monday_hours(owner.id)])
    await db.commit()

    availability = await client.get(
        f"/api/v1/storefront/{owner.slug}/available-slots",
        params={"service_id": str(offering.id), "date": BOOKING_DATE.isoformat()},
    )
    assert availability.status_code == 200, availability.text
    first = availability.json()["available_slots"][0]
    assert first == {
        "start_time": "10:00",
        "end_time": "11:00",
        "available": True,
        "available_staff": [{"id": str(member.id), "name": "Asha"}],
    }
    for unavailable_date in ("2030-01-05", "2030-01-06"):
        unavailable = await client.get(
            f"/api/v1/storefront/{owner.slug}/available-slots",
            params={"service_id": str(offering.id), "date": unavailable_date},
        )
        assert unavailable.status_code == 200
        assert unavailable.json()["available_slots"] == []

    response = await client.post(
        "/api/v1/bookings/initiate",
        json=booking_payload(
            str(offering.id),
            staff_member_id=str(member.id),
            price="0.01",
            end_time=None,
        ),
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["booking_status"] == "PENDING_PAYMENT"
    assert result["payment_status"] == "PENDING"
    assert result["end_time"] == "11:00:00"
    assert result["amount_to_pay"] == "300.00"
    assert result["hold_expires_at"] == "2030-01-06T00:10:00Z"
    assert result["booking_reference"].startswith("TI-20300107-")
    stored_customer = await db.scalar(select(Customer))
    assert stored_customer.phone_number == "+919876543211"


@pytest.mark.asyncio
async def test_two_simultaneous_explicit_staff_requests_one_wins(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(db, owner.id)
    member = await staff(db, owner.id, "Asha")
    db.add_all([assign(offering, member), monday_hours(owner.id)])
    await db.commit()
    payload = booking_payload(str(offering.id), staff_member_id=str(member.id))

    responses = await asyncio.gather(
        client.post("/api/v1/bookings/initiate", json=payload),
        client.post("/api/v1/bookings/initiate", json=payload),
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"]["code"] == "SLOT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_auto_assignment_is_deterministic_and_uses_available_staff(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(db, owner.id)
    first = await staff(db, owner.id, "First")
    second = await staff(db, owner.id, "Second")
    db.add_all([assign(offering, first), assign(offering, second), monday_hours(owner.id)])
    await db.commit()

    responses = await asyncio.gather(
        client.post("/api/v1/bookings/initiate", json=booking_payload(str(offering.id))),
        client.post(
            "/api/v1/bookings/initiate",
            json=booking_payload(str(offering.id), customer_phone="9876543212"),
        ),
    )
    assert [response.status_code for response in responses].count(201) == 2
    assigned = {response.json()["staff_member_id"] for response in responses}
    assert assigned == {str(first.id), str(second.id)}


@pytest.mark.asyncio
async def test_single_auto_assignment_uses_lowest_staff_uuid(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(db, owner.id)
    first = await staff(db, owner.id, "First")
    second = await staff(db, owner.id, "Second")
    db.add_all([assign(offering, first), assign(offering, second), monday_hours(owner.id)])
    await db.commit()
    response = await client.post(
        "/api/v1/bookings/initiate", json=booking_payload(str(offering.id))
    )
    assert response.status_code == 201
    assert response.json()["staff_member_id"] == str(min(first.id, second.id))


@pytest.mark.asyncio
async def test_staffless_services_share_merchant_resource(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    first = await service(db, owner.id, title="First")
    second = await service(db, owner.id, title="Second")
    db.add(monday_hours(owner.id))
    await db.commit()

    first_response = await client.post(
        "/api/v1/bookings/initiate", json=booking_payload(str(first.id))
    )
    second_response = await client.post(
        "/api/v1/bookings/initiate",
        json=booking_payload(str(second.id), customer_phone="9876543212"),
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["error"]["code"] == "SLOT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_expired_hold_does_not_occupy_capacity(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(db, owner.id)
    member = await staff(db, owner.id, "Asha")
    db.add_all([assign(offering, member), monday_hours(owner.id)])
    await db.flush()
    customer = Customer(
        merchant_id=owner.id,
        full_name="Old Customer",
        phone_number="+919876543219",
        total_bookings_count=0,
    )
    db.add(customer)
    await db.flush()
    db.add(
        Booking(
            booking_reference="TI-20300107-0000000001",
            merchant_id=owner.id,
            service_id=offering.id,
            customer_id=customer.id,
            staff_member_id=member.id,
            booking_date=BOOKING_DATE,
            start_time=time(10),
            end_time=time(11),
            custom_field_responses={},
            total_amount=offering.price,
            amount_to_pay=offering.advance_token_amount,
            booking_status=BookingStatus.PENDING_PAYMENT,
            payment_status=PaymentStatus.PENDING,
            hold_expires_at=FIXED_NOW - timedelta(seconds=1),
        )
    )
    await db.commit()
    response = await client.post(
        "/api/v1/bookings/initiate",
        json=booking_payload(str(offering.id), staff_member_id=str(member.id)),
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_appointment_detects_non_identical_interval_overlap(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(db, owner.id)
    member = await staff(db, owner.id, "Asha")
    db.add_all([assign(offering, member), monday_hours(owner.id)])
    await db.flush()
    customer = Customer(
        merchant_id=owner.id,
        full_name="Existing Customer",
        phone_number="+919876543219",
        total_bookings_count=0,
    )
    db.add(customer)
    await db.flush()
    db.add(
        Booking(
            booking_reference="TI-20300107-OVERLAP001",
            merchant_id=owner.id,
            service_id=offering.id,
            customer_id=customer.id,
            staff_member_id=member.id,
            booking_date=BOOKING_DATE,
            start_time=time(10, 30),
            end_time=time(11, 30),
            custom_field_responses={},
            total_amount=offering.price,
            amount_to_pay=offering.advance_token_amount,
            booking_status=BookingStatus.CONFIRMED,
            payment_status=PaymentStatus.FULLY_PAID,
            hold_expires_at=None,
        )
    )
    await db.commit()
    response = await client.post(
        "/api/v1/bookings/initiate",
        json=booking_payload(str(offering.id), staff_member_id=str(member.id)),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_batch_capacity_is_atomic(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(
        db,
        owner.id,
        mode=BookingMode.BATCH,
        duration=None,
        capacity=50,
        title="Dance",
    )
    schedule = BatchSchedule(
        merchant_id=owner.id,
        service_id=offering.id,
        day_of_week=1,
        start_time=time(19),
        end_time=time(20),
        max_capacity=2,
        is_active=True,
    )
    db.add(schedule)
    await db.commit()
    payloads = [
        booking_payload(
            str(offering.id),
            customer_phone=f"98765432{number:02d}",
            start_time=None,
            batch_schedule_id=str(schedule.id),
        )
        for number in range(3)
    ]
    responses = await asyncio.gather(
        *(client.post("/api/v1/bookings/initiate", json=payload) for payload in payloads)
    )
    assert [response.status_code for response in responses].count(201) == 2
    assert [response.status_code for response in responses].count(409) == 1
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"]["code"] == "BATCH_FULL"
    for response in responses:
        if response.status_code == 201:
            assert response.json()["start_time"] == "19:00:00"
            assert response.json()["end_time"] == "20:00:00"


@pytest.mark.asyncio
async def test_custom_order_lead_time_boundary_and_fields(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(
        db,
        owner.id,
        mode=BookingMode.CUSTOM_ORDER,
        title="Cake",
        duration=None,
        lead_hours=24,
        price="2000.00",
        advance="0.00",
    )
    db.add(
        OperatingHour(
            merchant_id=owner.id,
            day_of_week=1,
            open_time=time(5),
            close_time=time(23),
            is_closed=False,
        )
    )
    db.add(
        ServiceCustomField(
            merchant_id=owner.id,
            service_id=offering.id,
            field_label="Flavor",
            field_type=CustomFieldType.DROPDOWN,
            options=["Chocolate", "Vanilla"],
            is_required=True,
            display_order=0,
        )
    )
    db.add_all(
        [
            ServiceCustomField(
                merchant_id=owner.id,
                service_id=offering.id,
                field_label="Note",
                field_type=CustomFieldType.TEXT,
                options=None,
                is_required=True,
                display_order=1,
            ),
            ServiceCustomField(
                merchant_id=owner.id,
                service_id=offering.id,
                field_label="Eggless",
                field_type=CustomFieldType.BOOLEAN,
                options=None,
                is_required=True,
                display_order=2,
            ),
            ServiceCustomField(
                merchant_id=owner.id,
                service_id=offering.id,
                field_label="Reference",
                field_type=CustomFieldType.FILE_UPLOAD,
                options=None,
                is_required=False,
                display_order=3,
            ),
        ]
    )
    await db.commit()
    # FIXED_NOW is 05:30 in Kolkata, so the exact 24-hour boundary is 05:30 next day.
    base = booking_payload(
        str(offering.id),
        booking_date="2030-01-07",
        end_time="06:30",
        staff_member_id=None,
        custom_field_responses={"Flavor": "Chocolate", "Note": "Happy day", "Eggless": True},
    )
    before = await client.post(
        "/api/v1/bookings/initiate", json={**base, "start_time": "05:29"}
    )
    exact = await client.post(
        "/api/v1/bookings/initiate", json={**base, "start_time": "05:30"}
    )
    after = await client.post(
        "/api/v1/bookings/initiate",
        json={
            **base,
            "start_time": "05:31",
            "end_time": "06:31",
            "customer_phone": "9876543212",
        },
    )
    assert before.status_code == 409
    assert before.json()["error"]["code"] == "LEAD_TIME_REQUIRED"
    assert exact.status_code == 201, exact.text
    assert exact.json()["amount_to_pay"] == "2000.00"
    assert after.status_code == 201, after.text

    missing = await client.post(
        "/api/v1/bookings/initiate",
        json={**base, "start_time": "07:00", "end_time": "08:00", "custom_field_responses": {}},
    )
    assert missing.status_code == 422
    invalid = await client.post(
        "/api/v1/bookings/initiate",
        json={
            **base,
            "start_time": "07:00",
            "end_time": "08:00",
            "custom_field_responses": {
                "Flavor": "Strawberry",
                "Note": "",
                "Eggless": "yes",
                "Unknown": "x",
            },
        },
    )
    assert invalid.status_code == 422
    file_response = await client.post(
        "/api/v1/bookings/initiate",
        json={
            **base,
            "start_time": "07:00",
            "end_time": "08:00",
            "custom_field_responses": {
                "Flavor": "Chocolate",
                "Note": "Happy day",
                "Eggless": False,
                "Reference": "not-a-file",
            },
        },
    )
    assert file_response.status_code == 422


@pytest.mark.asyncio
async def test_public_filters_inactive_resources(client: AsyncClient, db: AsyncSession) -> None:
    owner = await merchant(db)
    active = await service(db, owner.id, title="Active")
    await service(db, owner.id, title="Hidden", active=False)
    await db.commit()
    response = await client.get(f"/api/v1/storefront/{owner.slug}")
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["services"]] == [str(active.id)]

    owner.is_active = False
    await db.commit()
    assert (await client.get(f"/api/v1/storefront/{owner.slug}")).status_code == 404


@pytest.mark.asyncio
async def test_confirmed_booking_always_occupies(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    async with session_maker() as db:
        owner = await merchant(db)
        offering = await service(db, owner.id)
        member = await staff(db, owner.id, "Asha")
        db.add_all([assign(offering, member), monday_hours(owner.id)])
        await db.commit()
    first = await client.post(
        "/api/v1/bookings/initiate",
        json=booking_payload(str(offering.id), staff_member_id=str(member.id)),
    )
    assert first.status_code == 201
    async with session_maker() as db:
        created = await db.scalar(select(Booking))
        created.booking_status = BookingStatus.CONFIRMED
        created.hold_expires_at = datetime(2020, 1, 1, tzinfo=UTC)
        await db.commit()
    second = await client.post(
        "/api/v1/bookings/initiate",
        json=booking_payload(
            str(offering.id), customer_phone="9876543212", staff_member_id=str(member.id)
        ),
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_reference_collision_retries(
    client: AsyncClient, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    async with session_maker() as db:
        owner = await merchant(db)
        offering = await service(db, owner.id)
        member = await staff(db, owner.id, "Asha")
        db.add_all([assign(offering, member), monday_hours(owner.id)])
        await db.commit()
    first = await client.post(
        "/api/v1/bookings/initiate",
        json=booking_payload(str(offering.id), staff_member_id=str(member.id)),
    )
    existing_reference = first.json()["booking_reference"]
    attempts = 0

    def references(value: date) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 5:
            return existing_reference
        return f"TI-{value:%Y%m%d}-RETRY00001"

    async with session_maker() as db, db.begin():
        booking = await initiate_booking(
            db,
            BookingInitiateRequest.model_validate(
                booking_payload(
                    str(offering.id),
                    start_time="11:00",
                    customer_phone="9876543212",
                    staff_member_id=str(member.id),
                )
            ),
            clock=lambda: FIXED_NOW,
            reference_factory=references,
        )
    assert attempts == 5
    assert booking.booking_reference.endswith("RETRY00001")


@pytest.mark.asyncio
async def test_inactive_assigned_staff_does_not_become_merchant_capacity(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner = await merchant(db)
    offering = await service(db, owner.id)
    inactive = await staff(db, owner.id, "Inactive", active=False)
    db.add_all([assign(offering, inactive), monday_hours(owner.id)])
    await db.commit()
    availability = await client.get(
        f"/api/v1/storefront/{owner.slug}/available-slots",
        params={"service_id": str(offering.id), "date": BOOKING_DATE.isoformat()},
    )
    assert availability.status_code == 200
    assert all(not slot["available"] for slot in availability.json()["available_slots"])
    response = await client.post(
        "/api/v1/bookings/initiate", json=booking_payload(str(offering.id))
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_UNAVAILABLE"
