import uuid
from datetime import time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Merchant, OperatingHour, Service, ServiceStaff, StaffMember
from app.models.enums import BookingMode, BusinessType


async def merchant(
    db: AsyncSession,
    *,
    slug: str = "test-studio",
    email: str = "owner@example.com",
    active: bool = True,
) -> Merchant:
    value = Merchant(
        business_name="Test Studio",
        slug=slug,
        business_type=BusinessType.SALON,
        owner_name="Test Owner",
        phone_number="+919876543210",
        email=email,
        password_hash=hash_password("password123"),
        timezone="Asia/Kolkata",
        is_active=active,
    )
    db.add(value)
    await db.flush()
    return value


async def service(
    db: AsyncSession,
    merchant_id: uuid.UUID,
    *,
    mode: BookingMode = BookingMode.APPOINTMENT,
    title: str = "Hair spa",
    price: str = "1500.00",
    advance: str = "300.00",
    duration: int | None = 60,
    capacity: int | None = None,
    lead_hours: int | None = None,
    active: bool = True,
) -> Service:
    value = Service(
        merchant_id=merchant_id,
        title=title,
        description="A test service",
        category="Featured",
        booking_mode=mode,
        price=Decimal(price),
        advance_token_amount=Decimal(advance),
        duration_minutes=duration,
        max_capacity=capacity,
        prep_lead_time_hours=lead_hours,
        is_active=active,
    )
    db.add(value)
    await db.flush()
    return value


async def staff(
    db: AsyncSession, merchant_id: uuid.UUID, name: str, *, active: bool = True
) -> StaffMember:
    value = StaffMember(merchant_id=merchant_id, name=name, is_active=active)
    db.add(value)
    await db.flush()
    return value


def assign(service_value: Service, staff_value: StaffMember) -> ServiceStaff:
    return ServiceStaff(
        merchant_id=service_value.merchant_id,
        service_id=service_value.id,
        staff_member_id=staff_value.id,
    )


def monday_hours(merchant_id: uuid.UUID) -> OperatingHour:
    return OperatingHour(
        merchant_id=merchant_id,
        day_of_week=1,
        open_time=time(10, 0),
        close_time=time(18, 0),
        is_closed=False,
    )
