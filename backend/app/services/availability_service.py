import uuid
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, require_aware_utc, utc_now
from app.models import (
    BatchSchedule,
    Booking,
    Merchant,
    OperatingHour,
    Service,
    ServiceStaff,
    StaffMember,
)
from app.models.enums import BookingMode, BookingStatus


def sunday_weekday(value: date) -> int:
    return (value.weekday() + 1) % 7


def occupying_booking(now_utc: datetime) -> Any:
    return or_(
        Booking.booking_status == BookingStatus.CONFIRMED,
        and_(
            Booking.booking_status == BookingStatus.PENDING_PAYMENT,
            Booking.hold_expires_at > require_aware_utc(now_utc),
        ),
    )


async def operating_hour_for(
    db: AsyncSession, merchant_id: uuid.UUID, booking_date: date
) -> OperatingHour | None:
    return await db.scalar(
        select(OperatingHour).where(
            OperatingHour.merchant_id == merchant_id,
            OperatingHour.day_of_week == sunday_weekday(booking_date),
        )
    )


def local_datetime(day: date, value: time, timezone: str) -> datetime:
    return datetime.combine(day, value, tzinfo=ZoneInfo(timezone))


async def appointment_availability(
    db: AsyncSession,
    merchant: Merchant,
    service: Service,
    booking_date: date,
    now_utc: datetime,
) -> list[dict[str, Any]]:
    hours = await operating_hour_for(db, merchant.id, booking_date)
    if (
        hours is None
        or hours.is_closed
        or hours.open_time is None
        or hours.close_time is None
        or service.duration_minutes is None
    ):
        return []

    now_local = require_aware_utc(now_utc).astimezone(ZoneInfo(merchant.timezone))
    opening = local_datetime(booking_date, hours.open_time, merchant.timezone)
    closing = local_datetime(booking_date, hours.close_time, merchant.timezone)
    if booking_date < now_local.date():
        return []

    assigned_staff_ids = list(
        await db.scalars(
            select(ServiceStaff.staff_member_id)
            .where(
                ServiceStaff.service_id == service.id,
                ServiceStaff.merchant_id == merchant.id,
            )
            .order_by(ServiceStaff.staff_member_id)
        )
    )
    staff = list(
        await db.scalars(
            select(StaffMember)
            .join(
                ServiceStaff,
                and_(
                    ServiceStaff.staff_member_id == StaffMember.id,
                    ServiceStaff.merchant_id == StaffMember.merchant_id,
                ),
            )
            .where(
                ServiceStaff.service_id == service.id,
                ServiceStaff.merchant_id == merchant.id,
                StaffMember.is_active.is_(True),
            )
            .order_by(StaffMember.id)
        )
    )

    staff_bookings: list[Booking] = []
    merchant_resource_bookings: list[Booking] = []
    if assigned_staff_ids:
        staff_bookings = list(
            await db.scalars(
                select(Booking).where(
                    Booking.merchant_id == merchant.id,
                    Booking.booking_date == booking_date,
                    Booking.staff_member_id.in_([member.id for member in staff]),
                    occupying_booking(now_utc),
                )
            )
        )
    else:
        merchant_resource_bookings = list(
            await db.scalars(
                select(Booking)
                .join(
                    Service,
                    and_(
                        Service.id == Booking.service_id,
                        Service.merchant_id == Booking.merchant_id,
                    ),
                )
                .where(
                    Booking.merchant_id == merchant.id,
                    Booking.booking_date == booking_date,
                    Booking.staff_member_id.is_(None),
                    Service.booking_mode == BookingMode.APPOINTMENT,
                    occupying_booking(now_utc),
                )
            )
        )

    slots: list[dict[str, Any]] = []
    slot_start = opening
    duration = timedelta(minutes=service.duration_minutes)
    while slot_start + duration <= closing:
        slot_end = slot_start + duration
        if slot_start >= now_local:
            if assigned_staff_ids:
                available_staff = [
                    {"id": str(member.id), "name": member.name}
                    for member in staff
                    if not any(
                        booking.staff_member_id == member.id
                        and booking.start_time < slot_end.time()
                        and booking.end_time > slot_start.time()
                        for booking in staff_bookings
                    )
                ]
                available = bool(available_staff)
            else:
                available_staff = []
                available = not any(
                    booking.start_time < slot_end.time()
                    and booking.end_time > slot_start.time()
                    for booking in merchant_resource_bookings
                )
            slots.append(
                {
                    "start_time": slot_start.strftime("%H:%M"),
                    "end_time": slot_end.strftime("%H:%M"),
                    "available": available,
                    "available_staff": available_staff,
                }
            )
        slot_start = slot_end
    return slots


async def batch_availability(
    db: AsyncSession,
    merchant: Merchant,
    service: Service,
    booking_date: date,
    now_utc: datetime,
) -> list[dict[str, Any]]:
    now_local = require_aware_utc(now_utc).astimezone(ZoneInfo(merchant.timezone))
    if booking_date < now_local.date():
        return []
    schedules = list(
        await db.scalars(
            select(BatchSchedule)
            .where(
                BatchSchedule.service_id == service.id,
                BatchSchedule.merchant_id == merchant.id,
                BatchSchedule.day_of_week == sunday_weekday(booking_date),
                BatchSchedule.is_active.is_(True),
            )
            .order_by(BatchSchedule.start_time, BatchSchedule.id)
        )
    )
    if not schedules:
        return []
    counts = dict(
        (
            await db.execute(
                select(Booking.batch_schedule_id, func.count(Booking.id))
                .where(
                    Booking.batch_schedule_id.in_([schedule.id for schedule in schedules]),
                    Booking.booking_date == booking_date,
                    occupying_booking(now_utc),
                )
                .group_by(Booking.batch_schedule_id)
            )
        ).all()
    )
    slots: list[dict[str, Any]] = []
    for schedule in schedules:
        session_start = local_datetime(booking_date, schedule.start_time, merchant.timezone)
        if session_start <= now_local:
            continue
        remaining = max(schedule.max_capacity - int(counts.get(schedule.id, 0)), 0)
        slots.append(
            {
                "batch_schedule_id": str(schedule.id),
                "start_time": schedule.start_time.strftime("%H:%M"),
                "end_time": schedule.end_time.strftime("%H:%M"),
                "max_capacity": schedule.max_capacity,
                "remaining_capacity": remaining,
                "available": remaining > 0,
            }
        )
    return slots


async def custom_order_availability(
    db: AsyncSession,
    merchant: Merchant,
    service: Service,
    booking_date: date,
    now_utc: datetime,
) -> tuple[list[dict[str, Any]], datetime]:
    hours = await operating_hour_for(db, merchant.id, booking_date)
    now_local = require_aware_utc(now_utc).astimezone(ZoneInfo(merchant.timezone))
    earliest = now_local + timedelta(hours=service.prep_lead_time_hours or 0)
    if (
        hours is None
        or hours.is_closed
        or hours.open_time is None
        or hours.close_time is None
        or booking_date < earliest.date()
    ):
        return [], earliest
    window_start = local_datetime(booking_date, hours.open_time, merchant.timezone)
    window_end = local_datetime(booking_date, hours.close_time, merchant.timezone)
    allowed_start = max(window_start, earliest)
    if allowed_start >= window_end:
        return [], earliest
    return (
        [
            {
                "start_time": allowed_start.strftime("%H:%M"),
                "end_time": window_end.strftime("%H:%M"),
                "business_open_time": hours.open_time.strftime("%H:%M"),
                "business_close_time": hours.close_time.strftime("%H:%M"),
                "available": True,
            }
        ],
        earliest,
    )


async def get_availability(
    db: AsyncSession,
    merchant: Merchant,
    service: Service,
    booking_date: date,
    clock: Clock = utc_now,
) -> tuple[list[dict[str, Any]], datetime | None]:
    now_utc = require_aware_utc(clock())
    if service.booking_mode == BookingMode.APPOINTMENT:
        return await appointment_availability(db, merchant, service, booking_date, now_utc), None
    if service.booking_mode == BookingMode.BATCH:
        return await batch_availability(db, merchant, service, booking_date, now_utc), None
    return await custom_order_availability(db, merchant, service, booking_date, now_utc)
