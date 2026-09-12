import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MerchantPaymentConfig(TimestampMixin, Base):
    __tablename__ = "merchant_payment_configs"
    __table_args__ = (
        UniqueConstraint("id", "merchant_id", name="uq_payment_config_id_merchant"),
        Index(
            "uq_current_payment_config",
            "merchant_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        CheckConstraint("provider = 'RAZORPAY'", name="provider_razorpay"),
        CheckConstraint("mode IN ('TEST', 'LIVE')", name="valid_mode"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), default="RAZORPAY", nullable=False)
    mode: Mapped[str] = mapped_column(String(8), default="TEST", nullable=False)
    key_id: Mapped[str] = mapped_column(String(100), nullable=False)
    key_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PaymentTransaction(TimestampMixin, Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["booking_id", "merchant_id"],
            ["bookings.id", "bookings.merchant_id"],
            ondelete="RESTRICT",
            name="fk_payment_booking_tenant",
        ),
        ForeignKeyConstraint(
            ["config_id", "merchant_id"],
            ["merchant_payment_configs.id", "merchant_payment_configs.merchant_id"],
            ondelete="RESTRICT",
            name="fk_payment_config_tenant",
        ),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("currency = 'INR'", name="inr_currency"),
        CheckConstraint(
            "status IN ('CREATING','CREATED','UNKNOWN','AUTHORIZED','CAPTURED','FAILED')",
            name="valid_payment_status",
        ),
        Index("ix_payment_booking", "booking_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="RAZORPAY", nullable=False)
    receipt: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="CREATING", nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_reason: Mapped[str | None] = mapped_column(String(80))
    reconciliation_state: Mapped[str | None] = mapped_column(String(40))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentWebhookEvent(TimestampMixin, Base):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint("config_id", "provider_event_id", name="uq_webhook_config_event"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("merchant_payment_configs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(20), default="RAZORPAY", nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(100))
    provider_payment_id: Mapped[str | None] = mapped_column(String(100))
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentCaptureAnomaly(TimestampMixin, Base):
    __tablename__ = "payment_capture_anomalies"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id", "provider_payment_id", name="uq_capture_anomaly_payment"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_payment_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
