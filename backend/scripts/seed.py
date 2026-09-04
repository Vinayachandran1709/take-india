"""Idempotent Phase 1 development seed data.

Run from backend with: python -m scripts.seed
"""

import asyncio
from datetime import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    BatchSchedule,
    Merchant,
    OperatingHour,
    Service,
    ServiceCustomField,
    ServiceStaff,
    StaffMember,
)
from app.models.enums import BookingMode, BusinessType, CustomFieldType

LOCAL_PASSWORD = "TakeIndiaLocal123!"


async def ensure_merchant(
    db: AsyncSession,
    *,
    business_name: str,
    slug: str,
    business_type: BusinessType,
    owner_name: str,
    phone_number: str,
    email: str,
) -> Merchant:
    merchant = await db.scalar(select(Merchant).where(Merchant.slug == slug))
    if merchant is None:
        merchant = Merchant(
            business_name=business_name,
            slug=slug,
            business_type=business_type,
            owner_name=owner_name,
            phone_number=phone_number,
            email=email,
            password_hash=hash_password(LOCAL_PASSWORD),
            timezone="Asia/Kolkata",
            is_active=True,
        )
        db.add(merchant)
        await db.flush()
    else:
        merchant.business_name = business_name
        merchant.business_type = business_type
        merchant.owner_name = owner_name
        merchant.phone_number = phone_number
        merchant.email = email
        merchant.timezone = "Asia/Kolkata"
        merchant.is_active = True
    return merchant


async def ensure_service(
    db: AsyncSession,
    merchant: Merchant,
    *,
    title: str,
    category: str,
    mode: BookingMode,
    price: str,
    advance: str,
    duration: int | None = None,
    capacity: int | None = None,
    lead_hours: int | None = None,
) -> Service:
    service = await db.scalar(
        select(Service).where(Service.merchant_id == merchant.id, Service.title == title)
    )
    values = {
        "category": category,
        "booking_mode": mode,
        "price": Decimal(price),
        "advance_token_amount": Decimal(advance),
        "duration_minutes": duration,
        "max_capacity": capacity,
        "prep_lead_time_hours": lead_hours,
        "is_active": True,
    }
    if service is None:
        service = Service(
            merchant_id=merchant.id,
            title=title,
            description=f"Phase 1 demo service from {merchant.business_name}",
            **values,
        )
        db.add(service)
        await db.flush()
    else:
        for field, value in values.items():
            setattr(service, field, value)
    return service


async def ensure_hours(
    db: AsyncSession,
    merchant: Merchant,
    *,
    open_at: time,
    close_at: time,
    open_days: set[int],
) -> None:
    existing = {
        row.day_of_week: row
        for row in await db.scalars(
            select(OperatingHour).where(OperatingHour.merchant_id == merchant.id)
        )
    }
    for day in range(7):
        row = existing.get(day)
        if row is None:
            row = OperatingHour(merchant_id=merchant.id, day_of_week=day)
            db.add(row)
        row.is_closed = day not in open_days
        row.open_time = open_at if day in open_days else None
        row.close_time = close_at if day in open_days else None


async def seed_data(db: AsyncSession) -> None:
    glow = await ensure_merchant(
        db,
        business_name="Glow Salon & Spa",
        slug="glow-salon-spa",
        business_type=BusinessType.SALON,
        owner_name="Glow Owner",
        phone_number="+919876543210",
        email="glow@example.com",
    )
    haircut = await ensure_service(
        db,
        glow,
        title="Signature Hair & Spa",
        category="Salon",
        mode=BookingMode.APPOINTMENT,
        price="1500.00",
        advance="300.00",
        duration=60,
    )
    for name in ("Asha", "Meera"):
        member = await db.scalar(
            select(StaffMember).where(
                StaffMember.merchant_id == glow.id, StaffMember.name == name
            )
        )
        if member is None:
            member = StaffMember(merchant_id=glow.id, name=name, is_active=True)
            db.add(member)
            await db.flush()
        else:
            member.is_active = True
        await db.execute(
            insert(ServiceStaff)
            .values(
                merchant_id=glow.id,
                service_id=haircut.id,
                staff_member_id=member.id,
            )
            .on_conflict_do_nothing()
        )
    await ensure_hours(
        db, glow, open_at=time(10), close_at=time(18), open_days={1, 2, 3, 4, 5, 6}
    )

    beatz = await ensure_merchant(
        db,
        business_name="Beatz Dance Studio",
        slug="beatz-dance-studio",
        business_type=BusinessType.ACADEMY,
        owner_name="Beatz Owner",
        phone_number="+919876543211",
        email="beatz@example.com",
    )
    dance = await ensure_service(
        db,
        beatz,
        title="Evening Dance Batch",
        category="Dance",
        mode=BookingMode.BATCH,
        price="2500.00",
        advance="0.00",
        capacity=12,
    )
    for day in (1, 3, 5):
        schedule = await db.scalar(
            select(BatchSchedule).where(
                BatchSchedule.service_id == dance.id,
                BatchSchedule.day_of_week == day,
                BatchSchedule.start_time == time(19),
            )
        )
        if schedule is None:
            schedule = BatchSchedule(
                merchant_id=beatz.id,
                service_id=dance.id,
                day_of_week=day,
                start_time=time(19),
                end_time=time(20),
                max_capacity=12,
                is_active=True,
            )
            db.add(schedule)
        else:
            schedule.end_time = time(20)
            schedule.max_capacity = 12
            schedule.is_active = True

    crumbs = await ensure_merchant(
        db,
        business_name="Sweet Crumbs",
        slug="sweet-crumbs",
        business_type=BusinessType.BAKERY,
        owner_name="Sweet Crumbs Owner",
        phone_number="+919876543212",
        email="crumbs@example.com",
    )
    cake = await ensure_service(
        db,
        crumbs,
        title="Custom Celebration Cake",
        category="Cakes",
        mode=BookingMode.CUSTOM_ORDER,
        price="2000.00",
        advance="0.00",
        lead_hours=24,
    )
    fields = (
        ("Flavor", CustomFieldType.DROPDOWN, ["Chocolate", "Vanilla", "Red Velvet"], True),
        ("Eggless", CustomFieldType.BOOLEAN, None, True),
        ("Cake Text", CustomFieldType.TEXT, None, False),
    )
    for order, (label, field_type, options, required) in enumerate(fields):
        field = await db.scalar(
            select(ServiceCustomField).where(
                ServiceCustomField.service_id == cake.id,
                ServiceCustomField.field_label == label,
            )
        )
        if field is None:
            field = ServiceCustomField(
                merchant_id=crumbs.id,
                service_id=cake.id,
                field_label=label,
            )
            db.add(field)
        field.field_type = field_type
        field.options = options
        field.is_required = required
        field.display_order = order
    await ensure_hours(
        db, crumbs, open_at=time(9), close_at=time(18), open_days={1, 2, 3, 4, 5, 6}
    )
    await db.commit()


async def main() -> None:
    settings = get_settings()
    if settings.environment.lower() in {"production", "prod"}:
        raise RuntimeError("Seed execution is forbidden in production")
    if settings.environment != "development":
        raise RuntimeError("Seed command requires ENVIRONMENT=development")
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionLocal() as db:
        await seed_data(db)
    print("Seeded Glow Salon & Spa, Beatz Dance Studio, and Sweet Crumbs.")
    print("Local-only login password: TakeIndiaLocal123!")


if __name__ == "__main__":
    asyncio.run(main())
