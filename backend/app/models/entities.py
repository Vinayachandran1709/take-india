import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    BookingMode,
    BookingStatus,
    BusinessType,
    CustomFieldType,
    PaymentStatus,
)


def enum_type(enum: type, name: str) -> Enum:
    return Enum(enum, name=name, values_callable=lambda values: [item.value for item in values])


class Merchant(TimestampMixin, Base):
    __tablename__ = "merchants"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_merchants_slug"),
        UniqueConstraint("email", name="uq_merchants_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    business_type: Mapped[BusinessType] = mapped_column(
        enum_type(BusinessType, "business_type"), nullable=False
    )
    owner_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    address: Mapped[str | None] = mapped_column(Text)
    google_place_id: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    services: Mapped[list["Service"]] = relationship(back_populates="merchant")
    staff_members: Mapped[list["StaffMember"]] = relationship(back_populates="merchant")


class StaffMember(Base):
    __tablename__ = "staff_members"
    __table_args__ = (UniqueConstraint("id", "merchant_id", name="uq_staff_id_merchant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    merchant: Mapped[Merchant] = relationship(back_populates="staff_members")


class Service(TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("id", "merchant_id", name="uq_services_id_merchant"),
        CheckConstraint("price >= 0", name="price_nonnegative"),
        CheckConstraint("advance_token_amount >= 0", name="advance_nonnegative"),
        CheckConstraint("advance_token_amount <= price", name="advance_not_above_price"),
        CheckConstraint(
            "booking_mode <> 'APPOINTMENT' OR "
            "(duration_minutes IS NOT NULL AND duration_minutes > 0)",
            name="appointment_duration",
        ),
        CheckConstraint(
            "booking_mode <> 'BATCH' OR (max_capacity IS NOT NULL AND max_capacity > 0)",
            name="batch_capacity",
        ),
        CheckConstraint(
            "booking_mode <> 'CUSTOM_ORDER' OR "
            "(prep_lead_time_hours IS NOT NULL AND prep_lead_time_hours >= 0)",
            name="custom_lead_time",
        ),
        Index("ix_services_merchant_active", "merchant_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    booking_mode: Mapped[BookingMode] = mapped_column(
        enum_type(BookingMode, "booking_mode"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    advance_token_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    max_capacity: Mapped[int | None] = mapped_column(Integer)
    prep_lead_time_hours: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    merchant: Mapped[Merchant] = relationship(back_populates="services")
    custom_fields: Mapped[list["ServiceCustomField"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )
    batch_schedules: Mapped[list["BatchSchedule"]] = relationship(
        back_populates="service"
    )


class ServiceStaff(Base):
    __tablename__ = "service_staff"
    __table_args__ = (
        PrimaryKeyConstraint("service_id", "staff_member_id", name="pk_service_staff"),
        ForeignKeyConstraint(
            ["service_id", "merchant_id"],
            ["services.id", "services.merchant_id"],
            ondelete="CASCADE",
            name="fk_service_staff_service_tenant",
        ),
        ForeignKeyConstraint(
            ["staff_member_id", "merchant_id"],
            ["staff_members.id", "staff_members.merchant_id"],
            ondelete="CASCADE",
            name="fk_service_staff_staff_tenant",
        ),
    )

    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class ServiceCustomField(Base):
    __tablename__ = "service_custom_fields"
    __table_args__ = (
        ForeignKeyConstraint(
            ["service_id", "merchant_id"],
            ["services.id", "services.merchant_id"],
            ondelete="CASCADE",
            name="fk_custom_fields_service_tenant",
        ),
        UniqueConstraint("service_id", "field_label", name="uq_custom_field_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_label: Mapped[str] = mapped_column(String(160), nullable=False)
    field_type: Mapped[CustomFieldType] = mapped_column(
        enum_type(CustomFieldType, "custom_field_type"), nullable=False
    )
    options: Mapped[list[str] | None] = mapped_column(JSONB)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    service: Mapped[Service] = relationship(back_populates="custom_fields")


class OperatingHour(Base):
    __tablename__ = "operating_hours"
    __table_args__ = (
        UniqueConstraint("merchant_id", "day_of_week", name="uq_operating_hours_day"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="valid_weekday"),
        CheckConstraint(
            "is_closed OR "
            "(open_time IS NOT NULL AND close_time IS NOT NULL AND open_time < close_time)",
            name="valid_open_interval",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    open_time: Mapped[time | None] = mapped_column(Time)
    close_time: Mapped[time | None] = mapped_column(Time)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BatchSchedule(Base):
    __tablename__ = "batch_schedules"
    __table_args__ = (
        UniqueConstraint("id", "merchant_id", name="uq_batch_schedule_id_merchant"),
        ForeignKeyConstraint(
            ["service_id", "merchant_id"],
            ["services.id", "services.merchant_id"],
            ondelete="RESTRICT",
            name="fk_batch_schedules_service_tenant",
        ),
        UniqueConstraint(
            "service_id", "day_of_week", "start_time", name="uq_batch_schedule_identity"
        ),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="valid_weekday"),
        CheckConstraint("start_time < end_time", name="valid_interval"),
        CheckConstraint("max_capacity > 0", name="positive_capacity"),
        Index("ix_batch_schedules_service_weekday", "service_id", "day_of_week"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    service: Mapped[Service] = relationship(back_populates="batch_schedules")


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("id", "merchant_id", name="uq_customers_id_merchant"),
        UniqueConstraint("merchant_id", "phone_number", name="uq_customer_merchant_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    total_bookings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_visit_date: Mapped[date | None] = mapped_column(Date)


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["service_id", "merchant_id"],
            ["services.id", "services.merchant_id"],
            ondelete="RESTRICT",
            name="fk_bookings_service_tenant",
        ),
        ForeignKeyConstraint(
            ["customer_id", "merchant_id"],
            ["customers.id", "customers.merchant_id"],
            ondelete="RESTRICT",
            name="fk_bookings_customer_tenant",
        ),
        ForeignKeyConstraint(
            ["staff_member_id", "merchant_id"],
            ["staff_members.id", "staff_members.merchant_id"],
            ondelete="RESTRICT",
            name="fk_bookings_staff_tenant",
        ),
        ForeignKeyConstraint(
            ["batch_schedule_id", "merchant_id"],
            ["batch_schedules.id", "batch_schedules.merchant_id"],
            ondelete="RESTRICT",
            name="fk_bookings_batch_tenant",
        ),
        UniqueConstraint("booking_reference", name="uq_bookings_reference"),
        UniqueConstraint("id", "merchant_id", name="uq_booking_id_merchant"),
        CheckConstraint("start_time < end_time", name="valid_interval"),
        CheckConstraint("total_amount >= 0", name="total_nonnegative"),
        CheckConstraint("amount_to_pay >= 0", name="payable_nonnegative"),
        CheckConstraint("amount_to_pay <= total_amount", name="payable_not_above_total"),
        CheckConstraint(
            "booking_status <> 'PENDING_PAYMENT' OR hold_expires_at IS NOT NULL",
            name="pending_requires_expiry",
        ),
        Index("ix_bookings_merchant_date", "merchant_id", "booking_date"),
        Index("ix_bookings_service_date", "service_id", "booking_date"),
        Index("ix_bookings_staff_date", "staff_member_id", "booking_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_reference: Mapped[str] = mapped_column(String(32), nullable=False)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    staff_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    batch_schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    custom_field_responses: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_to_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        enum_type(PaymentStatus, "payment_status"), nullable=False
    )
    booking_status: Mapped[BookingStatus] = mapped_column(
        enum_type(BookingStatus, "booking_status"), nullable=False
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    razorpay_order_id: Mapped[str | None] = mapped_column(String(255))
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(255))
    public_token_hash: Mapped[str | None] = mapped_column(String(64))
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    payment_review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    @property
    def balance_due(self) -> Decimal:
        return max(self.total_amount - self.amount_paid, Decimal("0"))
