import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentClock, DatabaseSession
from app.core.exceptions import AppError
from app.models import Merchant, Service, ServiceCustomField
from app.schemas.api import (
    AvailabilityResponse,
    CustomFieldOut,
    PublicMerchantOut,
    PublicServiceOut,
    StorefrontResponse,
)
from app.services.availability_service import get_availability

router = APIRouter(prefix="/storefront", tags=["storefront"])


async def public_merchant(slug: str, db: DatabaseSession) -> Merchant:
    merchant = await db.scalar(
        select(Merchant).where(Merchant.slug == slug, Merchant.is_active.is_(True))
    )
    if merchant is None:
        raise AppError("NOT_FOUND", "Storefront not found", 404)
    return merchant


async def public_service(
    merchant: Merchant, service_id: uuid.UUID, db: DatabaseSession
) -> Service:
    service = await db.scalar(
        select(Service).where(
            Service.id == service_id,
            Service.merchant_id == merchant.id,
            Service.is_active.is_(True),
        )
    )
    if service is None:
        raise AppError("NOT_FOUND", "Service not found", 404)
    return service


@router.get("/{slug}", response_model=StorefrontResponse)
async def get_storefront(slug: str, db: DatabaseSession) -> StorefrontResponse:
    merchant = await public_merchant(slug, db)
    services = list(
        await db.scalars(
            select(Service)
            .where(Service.merchant_id == merchant.id, Service.is_active.is_(True))
            .order_by(Service.category, Service.title, Service.id)
        )
    )
    fields = list(
        await db.scalars(
            select(ServiceCustomField)
            .where(
                ServiceCustomField.merchant_id == merchant.id,
                ServiceCustomField.service_id.in_([service.id for service in services]),
            )
            .order_by(ServiceCustomField.display_order, ServiceCustomField.id)
        )
    ) if services else []
    by_service = {service.id: [] for service in services}
    for field in fields:
        by_service[field.service_id].append(CustomFieldOut.model_validate(field))
    public_services = [
        PublicServiceOut(
            id=service.id,
            title=service.title,
            description=service.description,
            category=service.category,
            booking_mode=service.booking_mode,
            price=service.price,
            advance_token_amount=service.advance_token_amount,
            duration_minutes=service.duration_minutes,
            max_capacity=service.max_capacity,
            prep_lead_time_hours=service.prep_lead_time_hours,
            custom_fields=by_service[service.id],
        )
        for service in services
    ]
    return StorefrontResponse(
        merchant=PublicMerchantOut.model_validate(merchant),
        categories=sorted({service.category for service in services}),
        services=public_services,
    )


@router.get("/{slug}/available-slots", response_model=AvailabilityResponse)
async def available_slots(
    slug: str,
    service_id: uuid.UUID,
    db: DatabaseSession,
    clock: CurrentClock,
    booking_date: Annotated[date, Query(alias="date")],
) -> AvailabilityResponse:
    merchant = await public_merchant(slug, db)
    service = await public_service(merchant, service_id, db)
    slots, earliest = await get_availability(db, merchant, service, booking_date, clock)
    return AvailabilityResponse(
        service_id=service.id,
        booking_mode=service.booking_mode,
        date=booking_date,
        available_slots=slots,
        earliest_allowed_at=earliest,
    )
