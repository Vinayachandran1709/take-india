"""Public, token-authorized booking management contracts."""

from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.enums import BookingMode, BookingStatus


class ManageBookingResponse(BaseModel):
    booking_reference: str
    service_id: UUID
    merchant_id: UUID
    merchant_slug: str
    booking_mode: BookingMode
    booking_date: date
    start_time: time
    end_time: time
    booking_status: BookingStatus
    service_title: str
    business_name: str
    timezone: str
    can_cancel: bool
    can_reschedule: bool


class ManageRescheduleRequest(BaseModel):
    new_booking_date: date
    new_start_time: time

    @field_validator("new_start_time")
    @classmethod
    def require_local_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("Enter a local time without a timezone offset")
        return value
