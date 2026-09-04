import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentMerchant, DatabaseSession
from app.core.exceptions import AppError
from app.models import Service, ServiceStaff, StaffMember
from app.schemas.api import ServiceCreate, ServiceOut, ServiceUpdate, ServiceValues

router = APIRouter(prefix="/services", tags=["services"])


async def scoped_service(
    service_id: uuid.UUID, merchant_id: uuid.UUID, db: DatabaseSession
) -> Service:
    service = await db.scalar(
        select(Service).where(Service.id == service_id, Service.merchant_id == merchant_id)
    )
    if service is None:
        raise AppError("NOT_FOUND", "Service not found", 404)
    return service


async def staff_ids_for(service_id: uuid.UUID, db: DatabaseSession) -> list[uuid.UUID]:
    return list(
        await db.scalars(
            select(ServiceStaff.staff_member_id)
            .where(ServiceStaff.service_id == service_id)
            .order_by(ServiceStaff.staff_member_id)
        )
    )


async def service_out(service: Service, db: DatabaseSession) -> ServiceOut:
    result = ServiceOut.model_validate(service)
    result.staff_member_ids = await staff_ids_for(service.id, db)
    return result


async def validate_staff_ids(
    staff_ids: list[uuid.UUID], merchant_id: uuid.UUID, db: DatabaseSession
) -> None:
    if not staff_ids:
        return
    found = set(
        await db.scalars(
            select(StaffMember.id).where(
                StaffMember.id.in_(staff_ids),
                StaffMember.merchant_id == merchant_id,
                StaffMember.is_active.is_(True),
            )
        )
    )
    if found != set(staff_ids):
        raise AppError("VALIDATION_ERROR", "Every assigned staff member must be active", 400)


async def sync_staff(
    service: Service, staff_ids: list[uuid.UUID], db: DatabaseSession
) -> None:
    await validate_staff_ids(staff_ids, service.merchant_id, db)
    await db.execute(delete(ServiceStaff).where(ServiceStaff.service_id == service.id))
    db.add_all(
        [
            ServiceStaff(
                merchant_id=service.merchant_id,
                service_id=service.id,
                staff_member_id=staff_id,
            )
            for staff_id in staff_ids
        ]
    )


@router.get("", response_model=list[ServiceOut])
async def list_services(
    merchant: CurrentMerchant, db: DatabaseSession
) -> list[ServiceOut]:
    services = list(
        await db.scalars(
            select(Service)
            .where(Service.merchant_id == merchant.id)
            .order_by(Service.created_at, Service.id)
        )
    )
    return [await service_out(service, db) for service in services]


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreate, merchant: CurrentMerchant, db: DatabaseSession
) -> ServiceOut:
    values = payload.model_dump(exclude={"staff_member_ids"})
    service = Service(merchant_id=merchant.id, **values)
    db.add(service)
    await db.flush()
    await sync_staff(service, payload.staff_member_ids, db)
    await db.commit()
    await db.refresh(service)
    return await service_out(service, db)


@router.get("/{service_id}", response_model=ServiceOut)
async def get_service(
    service_id: uuid.UUID, merchant: CurrentMerchant, db: DatabaseSession
) -> ServiceOut:
    return await service_out(await scoped_service(service_id, merchant.id, db), db)


@router.patch("/{service_id}", response_model=ServiceOut)
async def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> ServiceOut:
    service = await scoped_service(service_id, merchant.id, db)
    existing_staff_ids = await staff_ids_for(service.id, db)
    changes = payload.model_dump(exclude_unset=True)
    requested_staff_ids = changes.pop("staff_member_ids", existing_staff_ids)
    merged = {
        "title": service.title,
        "description": service.description,
        "category": service.category,
        "booking_mode": service.booking_mode,
        "price": service.price,
        "advance_token_amount": service.advance_token_amount,
        "duration_minutes": service.duration_minutes,
        "max_capacity": service.max_capacity,
        "prep_lead_time_hours": service.prep_lead_time_hours,
        "is_active": service.is_active,
        "staff_member_ids": requested_staff_ids,
        **changes,
    }
    validated = ServiceValues.model_validate(merged)
    for field, value in validated.model_dump(exclude={"staff_member_ids"}).items():
        setattr(service, field, value)
    await sync_staff(service, validated.staff_member_ids, db)
    await db.commit()
    await db.refresh(service)
    return await service_out(service, db)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: uuid.UUID, merchant: CurrentMerchant, db: DatabaseSession
) -> Response:
    service = await scoped_service(service_id, merchant.id, db)
    service.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def commit_or_conflict(db: DatabaseSession, message: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError("RESOURCE_CONFLICT", message, 409) from exc

