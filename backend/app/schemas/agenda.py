"""Merchant-facing upcoming booking agenda."""

from datetime import date, time

from pydantic import BaseModel

from app.models.enums import BookingStatus


class AgendaBooking(BaseModel):
    booking_reference: str
    booking_date: date
    start_time: time
    end_time: time
    booking_status: BookingStatus
    service_title: str
    customer_name: str
    customer_phone: str


class AgendaResponse(BaseModel):
    today: date
    tomorrow: date
    timezone: str
    bookings: list[AgendaBooking]
