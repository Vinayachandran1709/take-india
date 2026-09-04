import secrets
import uuid
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, require_aware_utc, utc_now
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import (
    BatchSchedule,
    Booking,
    Customer,
    Merchant,
    OperatingHour,
    Service,
    ServiceCustomField,
    ServiceStaff,
    StaffMember,
)
from app.models.enums import BookingMode, BookingStatus, PaymentStatus
from app.schemas.api import BookingInitiateRequest
from app.services.availability_service import occupying_booking, sunday_weekday
from app.services.custom_fields import validate_custom_field_responses

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ReferenceFactory = Callable[[date], str]


def generate_booking_reference(booking_date: date) -> str:
    suffix = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(10))
    return f"TI-{booking_date:%Y%m%d}-{suffix}"


def local_datetime(day: date, value: time, timezone: str) -> datetime:
    return datetime.combine(day, value, tzinfo=ZoneInfo(timezone))


async def load_public_service(
    db: AsyncSession, service_id: uuid.UUID
) -> tuple[Merchant, Service]:
    row = (
        await db.execute(
            select(Merchant, Service)
            .join(Service, Service.merchant_id == Merchant.id)
            .where(
                Service.id == service_id,
                Service.is_active.is_(True),
                Merchant.is_active.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        raise AppError("NOT_FOUND", "Service not found", 404)
    return row[0], row[1]


async def validate_responses(
    db: AsyncSession, service: Service, responses: dict[str, Any]
) -> dict[str, Any]:
    fields = list(
        await db.scalars(
            select(ServiceCustomField)
            .where(
                ServiceCustomField.service_id == service.id,
                ServiceCustomField.merchant_id == service.merchant_id,
            )
            .order_by(ServiceCustomField.display_order, ServiceCustomField.id)
        )
    )
    return validate_custom_field_responses(fields, responses)


async def upsert_customer(
    db: AsyncSession, merchant_id: uuid.UUID, name: str, phone: str
) -> Customer:
    statement = (
        insert(Customer)
        .values(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            full_name=name,
            phone_number=phone,
            total_bookings_count=0,
        )
        .on_conflict_do_update(
            constraint="uq_customer_merchant_phone",
            set_={"full_name": name, "updated_at": func.now()},
        )
        .returning(Customer)
    )
    return (await db.scalars(statement)).one()


async def has_overlap(
    db: AsyncSession,
    *,
    merchant_id: uuid.UUID,
    booking_date: date,
    start_time: time,
    end_time: time,
    now_utc: datetime,
    staff_member_id: uuid.UUID | None,
) -> bool:
    query = select(Booking.id).where(
        Booking.merchant_id == merchant_id,
        Booking.booking_date == booking_date,
        Booking.start_time < end_time,
        Booking.end_time > start_time,
        occupying_booking(now_utc),
    )
    if staff_member_id is not None:
        query = query.where(Booking.staff_member_id == staff_member_id)
    else:
        query = query.join(
            Service,
            and_(
                Service.id == Booking.service_id,
                Service.merchant_id == Booking.merchant_id,
            ),
        ).where(
            Booking.staff_member_id.is_(None),
            Service.booking_mode == BookingMode.APPOINTMENT,
        )
    return (await db.scalar(query.limit(1))) is not None


async def appointment_resource(
    db: AsyncSession,
    *,
    merchant: Merchant,
    service: Service,
    requested_staff_id: uuid.UUID | None,
    booking_date: date,
    start_time: time,
    end_time: time,
    now_utc: datetime,
) -> uuid.UUID | None:
    assigned_ids = list(
        await db.scalars(
            select(ServiceStaff.staff_member_id)
            .where(
                ServiceStaff.service_id == service.id,
                ServiceStaff.merchant_id == merchant.id,
            )
            .order_by(ServiceStaff.staff_member_id)
        )
    )

    if requested_staff_id is not None:
        staff = await db.scalar(
            select(StaffMember)
            .join(
                ServiceStaff,
                and_(
                    ServiceStaff.staff_member_id == StaffMember.id,
                    ServiceStaff.merchant_id == StaffMember.merchant_id,
                ),
            )
            .where(
                StaffMember.id == requested_staff_id,
                StaffMember.merchant_id == merchant.id,
                StaffMember.is_active.is_(True),
                ServiceStaff.service_id == service.id,
            )
            .with_for_update(of=(StaffMember, ServiceStaff))
        )
        if staff is None:
            raise AppError("NOT_FOUND", "Staff member not found", 404)
        if await has_overlap(
            db,
            merchant_id=merchant.id,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            now_utc=now_utc,
            staff_member_id=staff.id,
        ):
            raise AppError("SLOT_UNAVAILABLE", "The requested slot is unavailable", 409)
        return staff.id

    if not assigned_ids:
        locked_merchant = await db.scalar(
            select(Merchant)
            .where(Merchant.id == merchant.id, Merchant.is_active.is_(True))
            .with_for_update()
        )
        if locked_merchant is None:
            raise AppError("NOT_FOUND", "Service not found", 404)
        if await has_overlap(
            db,
            merchant_id=merchant.id,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            now_utc=now_utc,
            staff_member_id=None,
        ):
            raise AppError("SLOT_UNAVAILABLE", "The requested slot is unavailable", 409)
        return None

    for candidate_id in assigned_ids:
        staff = await db.scalar(
            select(StaffMember)
            .join(
                ServiceStaff,
                and_(
                    ServiceStaff.staff_member_id == StaffMember.id,
                    ServiceStaff.merchant_id == StaffMember.merchant_id,
                ),
            )
            .where(
                StaffMember.id == candidate_id,
                StaffMember.merchant_id == merchant.id,
                StaffMember.is_active.is_(True),
                ServiceStaff.service_id == service.id,
            )
            .with_for_update(of=(StaffMember, ServiceStaff), skip_locked=True)
        )
        if staff is None:
            continue
        if not await has_overlap(
            db,
            merchant_id=merchant.id,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            now_utc=now_utc,
            staff_member_id=staff.id,
        ):
            return staff.id
    raise AppError("SLOT_UNAVAILABLE", "The requested slot is unavailable", 409)


async def appointment_values(
    db: AsyncSession,
    merchant: Merchant,
    service: Service,
    payload: BookingInitiateRequest,
    now_utc: datetime,
) -> tuple[time, time, uuid.UUID | None, None]:
    if payload.start_time is None or payload.end_time is not None or payload.batch_schedule_id:
        raise AppError(
            "VALIDATION_ERROR",
            "Appointments require start_time and do not accept end_time or batch_schedule_id",
            400,
        )
    if service.duration_minutes is None:
        raise AppError("SERVICE_CONFIGURATION_ERROR", "Appointment duration is missing", 409)
    hours = await db.scalar(
        select(OperatingHour).where(
            OperatingHour.merchant_id == merchant.id,
            OperatingHour.day_of_week == sunday_weekday(payload.booking_date),
        )
    )
    if hours is None or hours.is_closed or hours.open_time is None or hours.close_time is None:
        raise AppError("SLOT_UNAVAILABLE", "The business is closed on this date", 409)

    start = local_datetime(payload.booking_date, payload.start_time, merchant.timezone)
    end = start + timedelta(minutes=service.duration_minutes)
    opening = local_datetime(payload.booking_date, hours.open_time, merchant.timezone)
    closing = local_datetime(payload.booking_date, hours.close_time, merchant.timezone)
    elapsed = int((start - opening).total_seconds() // 60)
    if (
        start < require_aware_utc(now_utc).astimezone(ZoneInfo(merchant.timezone))
        or start < opening
        or end > closing
        or elapsed < 0
        or elapsed % service.duration_minutes != 0
    ):
        raise AppError("SLOT_UNAVAILABLE", "The requested slot is unavailable", 409)

    staff_id = await appointment_resource(
        db,
        merchant=merchant,
        service=service,
        requested_staff_id=payload.staff_member_id,
        booking_date=payload.booking_date,
        start_time=start.time(),
        end_time=end.time(),
        now_utc=now_utc,
    )
    return start.time(), end.time(), staff_id, None


async def batch_values(
    db: AsyncSession,
    merchant: Merchant,
    service: Service,
    payload: BookingInitiateRequest,
    now_utc: datetime,
) -> tuple[time, time, None, uuid.UUID]:
    if (
        payload.batch_schedule_id is None
        or payload.start_time is not None
        or payload.end_time is not None
        or payload.staff_member_id is not None
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "Batch bookings require only a batch_schedule_id and date",
            400,
        )
    schedule = await db.scalar(
        select(BatchSchedule)
        .where(
            BatchSchedule.id == payload.batch_schedule_id,
            BatchSchedule.service_id == service.id,
            BatchSchedule.merchant_id == merchant.id,
            BatchSchedule.is_active.is_(True),
        )
        .with_for_update()
    )
    if schedule is None:
        raise AppError("NOT_FOUND", "Batch schedule not found", 404)
    session_start = local_datetime(payload.booking_date, schedule.start_time, merchant.timezone)
    if (
        schedule.day_of_week != sunday_weekday(payload.booking_date)
        or session_start < require_aware_utc(now_utc).astimezone(ZoneInfo(merchant.timezone))
    ):
        raise AppError("BATCH_UNAVAILABLE", "This batch is unavailable on the selected date", 409)
    count = await db.scalar(
        select(func.count(Booking.id)).where(
            Booking.batch_schedule_id == schedule.id,
            Booking.booking_date == payload.booking_date,
            occupying_booking(now_utc),
        )
    )
    if int(count or 0) >= schedule.max_capacity:
        raise AppError("BATCH_FULL", "This batch has reached capacity", 409)
    return schedule.start_time, schedule.end_time, None, schedule.id


async def custom_order_values(
    db: AsyncSession,
    merchant: Merchant,
    service: Service,
    payload: BookingInitiateRequest,
    now_utc: datetime,
) -> tuple[time, time, None, None]:
    if (
        payload.start_time is None
        or payload.end_time is None
        or payload.staff_member_id is not None
        or payload.batch_schedule_id is not None
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "Custom orders require a start_time and end_time",
            400,
        )
    if payload.start_time >= payload.end_time:
        raise AppError("VALIDATION_ERROR", "start_time must be before end_time", 400)
    hours = await db.scalar(
        select(OperatingHour).where(
            OperatingHour.merchant_id == merchant.id,
            OperatingHour.day_of_week == sunday_weekday(payload.booking_date),
        )
    )
    if hours is None or hours.is_closed or hours.open_time is None or hours.close_time is None:
        raise AppError("WINDOW_UNAVAILABLE", "The business is closed on this date", 409)
    start = local_datetime(payload.booking_date, payload.start_time, merchant.timezone)
    end = local_datetime(payload.booking_date, payload.end_time, merchant.timezone)
    earliest = require_aware_utc(now_utc).astimezone(ZoneInfo(merchant.timezone)) + timedelta(
        hours=service.prep_lead_time_hours or 0
    )
    if payload.start_time < hours.open_time or payload.end_time > hours.close_time:
        raise AppError("WINDOW_UNAVAILABLE", "The requested window is outside operating hours", 409)
    if start < earliest:
        raise AppError("LEAD_TIME_REQUIRED", "The requested window is too soon", 409)
    return start.time(), end.time(), None, None


async def insert_booking_with_retry(
    db: AsyncSession,
    values: dict[str, Any],
    booking_date: date,
    reference_factory: ReferenceFactory,
) -> Booking:
    for _ in range(5):
        statement = (
            insert(Booking)
            .values(id=uuid.uuid4(), booking_reference=reference_factory(booking_date), **values)
            .on_conflict_do_nothing(index_elements=[Booking.booking_reference])
            .returning(Booking)
        )
        booking = (await db.scalars(statement)).one_or_none()
        if booking is not None:
            return booking
    raise AppError("REFERENCE_GENERATION_FAILED", "Could not allocate a booking reference", 503)


async def initiate_booking(
    db: AsyncSession,
    payload: BookingInitiateRequest,
    *,
    clock: Clock = utc_now,
    reference_factory: ReferenceFactory = generate_booking_reference,
) -> Booking:
    now_utc = require_aware_utc(clock())
    merchant, service = await load_public_service(db, payload.service_id)
    responses = await validate_responses(db, service, payload.custom_field_responses)

    if service.booking_mode == BookingMode.APPOINTMENT:
        start_time, end_time, staff_id, schedule_id = await appointment_values(
            db, merchant, service, payload, now_utc
        )
    elif service.booking_mode == BookingMode.BATCH:
        start_time, end_time, staff_id, schedule_id = await batch_values(
            db, merchant, service, payload, now_utc
        )
    else:
        start_time, end_time, staff_id, schedule_id = await custom_order_values(
            db, merchant, service, payload, now_utc
        )

    customer = await upsert_customer(
        db, merchant.id, payload.customer_name, payload.customer_phone
    )
    payable = (
        service.advance_token_amount
        if service.advance_token_amount > Decimal("0.00")
        else service.price
    )
    hold_expires_at = now_utc + timedelta(minutes=get_settings().booking_hold_minutes)
    return await insert_booking_with_retry(
        db,
        {
            "merchant_id": merchant.id,
            "service_id": service.id,
            "customer_id": customer.id,
            "staff_member_id": staff_id,
            "batch_schedule_id": schedule_id,
            "booking_date": payload.booking_date,
            "start_time": start_time,
            "end_time": end_time,
            "custom_field_responses": responses,
            "total_amount": service.price,
            "amount_to_pay": payable,
            "payment_status": PaymentStatus.PENDING,
            "booking_status": BookingStatus.PENDING_PAYMENT,
            "hold_expires_at": hold_expires_at,
        },
        payload.booking_date,
        reference_factory,
    )
