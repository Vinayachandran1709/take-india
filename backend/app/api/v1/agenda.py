"""Authenticated merchant agenda for the booking-first V1 dashboard."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response
from sqlalchemy import and_, select

from app.api.dependencies import CurrentClock, CurrentMerchant, DatabaseSession
from app.core.clock import require_aware_utc
from app.models import Booking, Customer, Service
from app.models.enums import BookingStatus
from app.schemas.agenda import AgendaBooking, AgendaResponse

router = APIRouter(prefix="/merchants/me", tags=["merchant agenda"])


@router.get("/agenda", response_model=AgendaResponse)
async def upcoming_agenda(
    merchant: CurrentMerchant, db: DatabaseSession, clock: CurrentClock, response: Response
) -> AgendaResponse:
    response.headers["Cache-Control"] = "no-store"
    today = require_aware_utc(clock()).astimezone(ZoneInfo(merchant.timezone)).date()
    tomorrow = today + timedelta(days=1)
    rows = await db.execute(
        select(Booking, Service.title, Customer.full_name, Customer.phone_number)
        .join(
            Service,
            and_(Service.id == Booking.service_id, Service.merchant_id == Booking.merchant_id),
        )
        .join(
            Customer,
            and_(Customer.id == Booking.customer_id, Customer.merchant_id == Booking.merchant_id),
        )
        .where(
            Booking.merchant_id == merchant.id,
            Booking.booking_date.between(today, tomorrow),
            Booking.booking_status == BookingStatus.CONFIRMED,
        )
        .order_by(Booking.booking_date.asc(), Booking.start_time.asc(), Booking.id.asc())
    )
    bookings = [
        AgendaBooking(
            booking_reference=booking.booking_reference,
            booking_date=booking.booking_date,
            start_time=booking.start_time,
            end_time=booking.end_time,
            booking_status=booking.booking_status,
            service_title=service_title,
            customer_name=customer_name,
            customer_phone=customer_phone,
        )
        for booking, service_title, customer_name, customer_phone in rows.all()
    ]
    return AgendaResponse(
        today=today, tomorrow=tomorrow, timezone=merchant.timezone, bookings=bookings
    )
