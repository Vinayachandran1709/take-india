import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.phone import InvalidPhoneNumber, normalize_phone_number
from app.models.enums import BookingMode, BusinessType, CustomFieldType
from app.schemas.billing import BillingSummary


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


def normalized_phone(value: str) -> str:
    try:
        return normalize_phone_number(value)
    except InvalidPhoneNumber as exc:
        raise ValueError(str(exc)) from exc


class SignupRequest(ApiModel):
    business_name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=120)
    business_type: BusinessType
    owner_name: str = Field(min_length=2, max_length=120)
    phone_number: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str = "Asia/Kolkata"

    _normalize_phone = field_validator("phone_number")(normalized_phone)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Enter a valid IANA timezone") from exc
        return value


class LoginRequest(ApiModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"


class MerchantOut(ApiModel):
    id: uuid.UUID
    business_name: str
    slug: str
    business_type: BusinessType
    owner_name: str
    phone_number: str
    email: EmailStr
    logo_url: str | None
    cover_image_url: str | None
    address: str | None
    google_place_id: str | None
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    billing: BillingSummary | None = None


class AuthResponse(TokenResponse):
    merchant: MerchantOut


class MerchantUpdate(ApiModel):
    business_name: str | None = Field(default=None, min_length=2, max_length=160)
    owner_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone_number: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    cover_image_url: str | None = Field(default=None, max_length=500)
    address: str | None = None
    timezone: str | None = None

    @field_validator("phone_number")
    @classmethod
    def normalize_optional_phone(cls, value: str | None) -> str | None:
        return normalized_phone(value) if value is not None else None

    @field_validator("timezone")
    @classmethod
    def validate_optional_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Enter a valid IANA timezone") from exc
        return value


class StaffCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)


class StaffUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None


class StaffOut(ApiModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime


class ServiceValues(ApiModel):
    title: str = Field(min_length=2, max_length=160)
    description: str | None = None
    category: str = Field(min_length=1, max_length=100)
    booking_mode: BookingMode
    price: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    advance_token_amount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    duration_minutes: int | None = None
    max_capacity: int | None = None
    prep_lead_time_hours: int | None = None
    reschedule_cutoff_hours: int | None = Field(default=None, ge=0)
    allow_cancellations: bool = False
    cancel_cutoff_hours: int = Field(default=0, ge=0)
    is_active: bool = True
    staff_member_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "ServiceValues":
        if self.advance_token_amount > self.price:
            raise ValueError("advance_token_amount cannot exceed price")
        if self.booking_mode == BookingMode.APPOINTMENT:
            if self.duration_minutes is None or self.duration_minutes <= 0:
                raise ValueError("duration_minutes must be positive for appointments")
        elif self.booking_mode == BookingMode.BATCH:
            if self.max_capacity is None or self.max_capacity <= 0:
                raise ValueError("max_capacity must be positive for batch services")
        elif self.prep_lead_time_hours is None or self.prep_lead_time_hours < 0:
            raise ValueError("prep_lead_time_hours is required for custom orders")
        if len(set(self.staff_member_ids)) != len(self.staff_member_ids):
            raise ValueError("staff_member_ids cannot contain duplicates")
        return self


class ServiceCreate(ServiceValues):
    pass


class ServiceUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    booking_mode: BookingMode | None = None
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    advance_token_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    duration_minutes: int | None = None
    max_capacity: int | None = None
    prep_lead_time_hours: int | None = None
    reschedule_cutoff_hours: int | None = Field(default=None, ge=0)
    allow_cancellations: bool | None = None
    cancel_cutoff_hours: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    staff_member_ids: list[uuid.UUID] | None = None


class ServiceOut(ApiModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: str
    booking_mode: BookingMode
    price: Decimal
    advance_token_amount: Decimal
    duration_minutes: int | None
    max_capacity: int | None
    prep_lead_time_hours: int | None
    reschedule_cutoff_hours: int | None
    allow_cancellations: bool
    cancel_cutoff_hours: int
    is_active: bool
    staff_member_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CustomFieldCreate(ApiModel):
    field_label: str = Field(min_length=1, max_length=160)
    field_type: CustomFieldType
    options: list[str] | None = None
    is_required: bool = False
    display_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_field(self) -> "CustomFieldCreate":
        if self.field_type == CustomFieldType.DROPDOWN:
            if not self.options or any(not option.strip() for option in self.options):
                raise ValueError("Dropdown fields require non-empty options")
            if len(set(self.options)) != len(self.options):
                raise ValueError("Dropdown options must be unique")
        elif self.options:
            raise ValueError("Only dropdown fields may define options")
        if self.field_type == CustomFieldType.FILE_UPLOAD and self.is_required:
            raise ValueError("FILE_UPLOAD cannot be required in Phase 1")
        return self


class CustomFieldUpdate(ApiModel):
    field_label: str | None = Field(default=None, min_length=1, max_length=160)
    field_type: CustomFieldType | None = None
    options: list[str] | None = None
    is_required: bool | None = None
    display_order: int | None = Field(default=None, ge=0)


class CustomFieldOut(ApiModel):
    id: uuid.UUID
    service_id: uuid.UUID
    field_label: str
    field_type: CustomFieldType
    options: list[str] | None
    is_required: bool
    display_order: int


class OperatingHourIn(ApiModel):
    day_of_week: int = Field(ge=0, le=6)
    open_time: time | None = None
    close_time: time | None = None
    is_closed: bool = False

    @model_validator(mode="after")
    def validate_interval(self) -> "OperatingHourIn":
        if self.is_closed:
            self.open_time = None
            self.close_time = None
        elif self.open_time is None or self.close_time is None or self.open_time >= self.close_time:
            raise ValueError("Open days require open_time before close_time")
        return self


class OperatingHourOut(OperatingHourIn):
    id: uuid.UUID


class OperatingHoursPut(ApiModel):
    days: list[OperatingHourIn] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def unique_days(self) -> "OperatingHoursPut":
        weekdays = [day.day_of_week for day in self.days]
        if len(set(weekdays)) != len(weekdays):
            raise ValueError("Each day_of_week may appear only once")
        return self


class BatchScheduleCreate(ApiModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    max_capacity: int = Field(gt=0)
    is_active: bool = True

    @model_validator(mode="after")
    def valid_interval(self) -> "BatchScheduleCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class BatchScheduleUpdate(ApiModel):
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    max_capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class BatchScheduleOut(BatchScheduleCreate):
    id: uuid.UUID
    service_id: uuid.UUID


class PublicMerchantOut(ApiModel):
    business_name: str
    slug: str
    business_type: BusinessType
    logo_url: str | None
    cover_image_url: str | None
    address: str | None
    timezone: str
    accepting_bookings: bool = True


class PublicStaffOut(ApiModel):
    id: uuid.UUID
    name: str


class PublicServiceOut(ApiModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: str
    booking_mode: BookingMode
    price: Decimal
    advance_token_amount: Decimal
    duration_minutes: int | None
    max_capacity: int | None
    prep_lead_time_hours: int | None
    reschedule_cutoff_hours: int | None
    allow_cancellations: bool
    cancel_cutoff_hours: int
    custom_fields: list[CustomFieldOut]


class StorefrontResponse(ApiModel):
    merchant: PublicMerchantOut
    categories: list[str]
    services: list[PublicServiceOut]


class AvailabilityResponse(ApiModel):
    service_id: uuid.UUID
    booking_mode: BookingMode
    date: date
    available_slots: list[dict[str, Any]]
    earliest_allowed_at: datetime | None = None


class BookingInitiateRequest(ApiModel):
    service_id: uuid.UUID
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: str
    booking_date: date
    start_time: time | None = None
    end_time: time | None = None
    staff_member_id: uuid.UUID | None = None
    batch_schedule_id: uuid.UUID | None = None
    custom_field_responses: dict[str, Any] = Field(default_factory=dict)

    _normalize_phone = field_validator("customer_phone")(normalized_phone)


class BookingInitiateResponse(ApiModel):
    public_booking_token: str | None = None
    management_token: str | None = None
    booking_reference: str
    booking_status: str
    payment_status: str
    booking_date: date
    start_time: time
    end_time: time
    staff_member_id: uuid.UUID | None
    batch_schedule_id: uuid.UUID | None
    amount_to_pay: Decimal
    currency: str = "INR"
    hold_expires_at: datetime | None
