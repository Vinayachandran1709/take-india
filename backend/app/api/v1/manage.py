"""Passwordless customer booking management using opaque bearer links."""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentClock, DatabaseSession
from app.core.clock import require_aware_utc
from app.models import BatchSchedule, Booking, Customer, Merchant, Service
from app.models.enums import BookingMode, BookingStatus
from app.schemas.manage import ManageBookingResponse, ManageRescheduleRequest
from app.services.availability_service import (
    local_datetime,
    occupying_booking,
    operating_hour_for,
    sunday_weekday,
)
from app.services.booking_service import appointment_resource
from app.services.whatsapp_service import send_reschedule_confirmation

router = APIRouter(prefix="/manage", tags=["management"])
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
logger = logging.getLogger(__name__)


def _private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"


async def _get_booking_by_token(
    db: AsyncSession, token: str, *, for_update: bool = False
) -> tuple[Booking, Service, Merchant]:
    if _TOKEN_PATTERN.fullmatch(token) is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    statement = (
        select(Booking, Service, Merchant)
        .join(
            Service,
            and_(Service.id == Booking.service_id, Service.merchant_id == Booking.merchant_id),
        )
        .join(Merchant, Merchant.id == Booking.merchant_id)
        .where(Booking.management_token_hash == digest)
    )
    if for_update:
        statement = statement.with_for_update(of=Booking)
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return row[0], row[1], row[2]


def _permissions(
    booking: Booking, service: Service, merchant: Merchant, now_utc: datetime
) -> tuple[bool, bool]:
    start = local_datetime(booking.booking_date, booking.start_time, merchant.timezone)
    remaining = start - require_aware_utc(now_utc)
    confirmed = booking.booking_status == BookingStatus.CONFIRMED
    can_cancel = (
        confirmed
        and service.allow_cancellations
        and remaining > timedelta(hours=service.cancel_cutoff_hours)
    )
    can_reschedule = (
        confirmed
        and service.reschedule_cutoff_hours is not None
        and remaining > timedelta(hours=service.reschedule_cutoff_hours)
    )
    return can_cancel, can_reschedule


@router.get("/{token}", response_model=ManageBookingResponse)
async def get_managed_booking(
    token: str, db: DatabaseSession, clock: CurrentClock, response: Response
) -> ManageBookingResponse:
    _private_response(response)
    booking, service, merchant = await _get_booking_by_token(db, token)
    can_cancel, can_reschedule = _permissions(booking, service, merchant, clock())
    return ManageBookingResponse(
        booking_reference=booking.booking_reference,
        service_id=service.id,
        merchant_id=merchant.id,
        merchant_slug=merchant.slug,
        booking_mode=service.booking_mode,
        booking_date=booking.booking_date,
        start_time=booking.start_time,
        end_time=booking.end_time,
        booking_status=booking.booking_status,
        service_title=service.title,
        business_name=merchant.business_name,
        timezone=merchant.timezone,
        can_cancel=can_cancel,
        can_reschedule=can_reschedule,
    )


@router.post("/{token}/cancel")
async def cancel_managed_booking(
    token: str, db: DatabaseSession, clock: CurrentClock, response: Response
) -> dict[str, str]:
    _private_response(response)
    booking, service, merchant = await _get_booking_by_token(db, token, for_update=True)
    can_cancel, _ = _permissions(booking, service, merchant, clock())
    if not can_cancel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cancellation not permitted or cutoff time passed",
        )
    booking.booking_status = BookingStatus.CANCELLED
    await db.commit()
    return {"message": "Booking cancelled"}


@router.post("/{token}/reschedule")
async def reschedule_managed_booking(
    token: str,
    payload: ManageRescheduleRequest,
    db: DatabaseSession,
    clock: CurrentClock,
    response: Response,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    _private_response(response)
    booking, service, merchant = await _get_booking_by_token(db, token, for_update=True)
    now_utc = require_aware_utc(clock())
    _, can_reschedule = _permissions(booking, service, merchant, now_utc)
    if not can_reschedule:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rescheduling not permitted or cutoff time passed",
        )

    new_start = local_datetime(payload.new_booking_date, payload.new_start_time, merchant.timezone)
    if new_start <= now_utc:
        raise HTTPException(status_code=400, detail="Choose a future booking time")

    if service.booking_mode == BookingMode.BATCH:
        schedule = await db.scalar(
            select(BatchSchedule)
            .where(
                BatchSchedule.service_id == service.id,
                BatchSchedule.merchant_id == merchant.id,
                BatchSchedule.day_of_week == sunday_weekday(payload.new_booking_date),
                BatchSchedule.start_time == payload.new_start_time,
                BatchSchedule.is_active.is_(True),
            )
            .with_for_update()
        )
        if schedule is None:
            raise HTTPException(status_code=400, detail="Choose an available class time")
        count = await db.scalar(
            select(func.count(Booking.id)).where(
                Booking.batch_schedule_id == schedule.id,
                Booking.booking_date == payload.new_booking_date,
                Booking.id != booking.id,
                occupying_booking(now_utc),
            )
        )
        if int(count or 0) >= schedule.max_capacity:
            raise HTTPException(status_code=409, detail="This class is full")
        booking.batch_schedule_id = schedule.id
        booking.end_time = schedule.end_time
    else:
        duration = (
            timedelta(minutes=service.duration_minutes)
            if service.booking_mode == BookingMode.APPOINTMENT and service.duration_minutes
            else datetime.combine(booking.booking_date, booking.end_time)
            - datetime.combine(booking.booking_date, booking.start_time)
        )
        new_end = new_start + duration
        if duration <= timedelta(0) or new_end.date() != payload.new_booking_date:
            raise HTTPException(status_code=400, detail="Choose a time that fits on one day")
        hours = await operating_hour_for(db, merchant.id, payload.new_booking_date)
        if hours is None or hours.is_closed or hours.open_time is None or hours.close_time is None:
            raise HTTPException(status_code=409, detail="The business is closed at that time")
        if payload.new_start_time < hours.open_time or new_end.time() > hours.close_time:
            raise HTTPException(status_code=409, detail="Choose a time within business hours")
        if service.booking_mode == BookingMode.APPOINTMENT:
            if service.duration_minutes is None or service.duration_minutes <= 0:
                raise HTTPException(
                    status_code=409, detail="This service has no valid appointment duration"
                )
            opening = local_datetime(payload.new_booking_date, hours.open_time, merchant.timezone)
            elapsed = int((new_start - opening).total_seconds() // 60)
            if elapsed < 0 or elapsed % service.duration_minutes != 0:
                raise HTTPException(status_code=409, detail="Choose an available appointment time")
            booking.staff_member_id = await appointment_resource(
                db,
                merchant=merchant,
                service=service,
                requested_staff_id=booking.staff_member_id,
                booking_date=payload.new_booking_date,
                start_time=payload.new_start_time,
                end_time=new_end.time(),
                now_utc=now_utc,
                exclude_booking_id=booking.id,
            )
        elif new_start < now_utc.astimezone(ZoneInfo(merchant.timezone)) + timedelta(
            hours=service.prep_lead_time_hours or 0
        ):
            raise HTTPException(status_code=409, detail="This order needs more preparation time")
        booking.end_time = new_end.time().replace(tzinfo=None)

    booking.booking_date = payload.new_booking_date
    booking.start_time = payload.new_start_time
    phone_number = await db.scalar(
        select(Customer.phone_number).where(
            Customer.id == booking.customer_id,
            Customer.merchant_id == merchant.id,
        )
    )
    service_title = service.title
    business_name = merchant.business_name
    new_datetime_str = new_start.strftime("%d %b %Y, %I:%M %p")
    manage_url = f"https://typein.co/manage/{token}"
    await db.commit()
    if phone_number:
        background_tasks.add_task(
            send_reschedule_confirmation,
            phone_number,
            service_title,
            business_name,
            new_datetime_str,
            manage_url,
        )
    else:
        logger.warning("WhatsApp reschedule confirmation skipped: customer phone was not found")
    return {"message": "Booking rescheduled"}
