import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.dependencies import CurrentMerchant, DatabaseSession
from app.api.v1.services import commit_or_conflict, scoped_service
from app.core.exceptions import AppError
from app.models import BatchSchedule, OperatingHour, ServiceCustomField
from app.models.enums import BookingMode
from app.schemas.api import (
    BatchScheduleCreate,
    BatchScheduleOut,
    BatchScheduleUpdate,
    CustomFieldCreate,
    CustomFieldOut,
    CustomFieldUpdate,
    OperatingHourOut,
    OperatingHoursPut,
)

router = APIRouter(tags=["configuration"])


async def scoped_custom_field(
    service_id: uuid.UUID,
    field_id: uuid.UUID,
    merchant_id: uuid.UUID,
    db: DatabaseSession,
) -> ServiceCustomField:
    field = await db.scalar(
        select(ServiceCustomField).where(
            ServiceCustomField.id == field_id,
            ServiceCustomField.service_id == service_id,
            ServiceCustomField.merchant_id == merchant_id,
        )
    )
    if field is None:
        raise AppError("NOT_FOUND", "Custom field not found", 404)
    return field


@router.get("/services/{service_id}/custom-fields", response_model=list[CustomFieldOut])
async def list_custom_fields(
    service_id: uuid.UUID, merchant: CurrentMerchant, db: DatabaseSession
) -> list[ServiceCustomField]:
    await scoped_service(service_id, merchant.id, db)
    return list(
        await db.scalars(
            select(ServiceCustomField)
            .where(
                ServiceCustomField.service_id == service_id,
                ServiceCustomField.merchant_id == merchant.id,
            )
            .order_by(ServiceCustomField.display_order, ServiceCustomField.id)
        )
    )


@router.post(
    "/services/{service_id}/custom-fields",
    response_model=CustomFieldOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_field(
    service_id: uuid.UUID,
    payload: CustomFieldCreate,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> ServiceCustomField:
    await scoped_service(service_id, merchant.id, db)
    field = ServiceCustomField(
        merchant_id=merchant.id,
        service_id=service_id,
        **payload.model_dump(),
    )
    db.add(field)
    await commit_or_conflict(db, "A custom field with this label already exists")
    await db.refresh(field)
    return field


@router.patch(
    "/services/{service_id}/custom-fields/{field_id}", response_model=CustomFieldOut
)
async def update_custom_field(
    service_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: CustomFieldUpdate,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> ServiceCustomField:
    field = await scoped_custom_field(service_id, field_id, merchant.id, db)
    merged = CustomFieldCreate(
        field_label=payload.field_label or field.field_label,
        field_type=payload.field_type or field.field_type,
        options=payload.options if "options" in payload.model_fields_set else field.options,
        is_required=(
            payload.is_required
            if payload.is_required is not None
            else field.is_required
        ),
        display_order=(
            payload.display_order
            if payload.display_order is not None
            else field.display_order
        ),
    )
    for key, value in merged.model_dump().items():
        setattr(field, key, value)
    await commit_or_conflict(db, "A custom field with this label already exists")
    await db.refresh(field)
    return field


@router.delete(
    "/services/{service_id}/custom-fields/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_custom_field(
    service_id: uuid.UUID,
    field_id: uuid.UUID,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> Response:
    field = await scoped_custom_field(service_id, field_id, merchant.id, db)
    await db.delete(field)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/operating-hours", response_model=list[OperatingHourOut])
async def list_operating_hours(
    merchant: CurrentMerchant, db: DatabaseSession
) -> list[OperatingHour]:
    return list(
        await db.scalars(
            select(OperatingHour)
            .where(OperatingHour.merchant_id == merchant.id)
            .order_by(OperatingHour.day_of_week)
        )
    )


@router.put("/operating-hours", response_model=list[OperatingHourOut])
async def put_operating_hours(
    payload: OperatingHoursPut, merchant: CurrentMerchant, db: DatabaseSession
) -> list[OperatingHour]:
    existing = {
        hour.day_of_week: hour
        for hour in await db.scalars(
            select(OperatingHour).where(OperatingHour.merchant_id == merchant.id)
        )
    }
    for value in payload.days:
        hour = existing.get(value.day_of_week)
        if hour is None:
            hour = OperatingHour(merchant_id=merchant.id, day_of_week=value.day_of_week)
            db.add(hour)
            existing[value.day_of_week] = hour
        hour.open_time = value.open_time
        hour.close_time = value.close_time
        hour.is_closed = value.is_closed
    await db.commit()
    return list(
        await db.scalars(
            select(OperatingHour)
            .where(OperatingHour.merchant_id == merchant.id)
            .order_by(OperatingHour.day_of_week)
        )
    )


async def scoped_batch_schedule(
    service_id: uuid.UUID,
    schedule_id: uuid.UUID,
    merchant_id: uuid.UUID,
    db: DatabaseSession,
) -> BatchSchedule:
    schedule = await db.scalar(
        select(BatchSchedule).where(
            BatchSchedule.id == schedule_id,
            BatchSchedule.service_id == service_id,
            BatchSchedule.merchant_id == merchant_id,
        )
    )
    if schedule is None:
        raise AppError("NOT_FOUND", "Batch schedule not found", 404)
    return schedule


@router.get(
    "/services/{service_id}/batch-schedules", response_model=list[BatchScheduleOut]
)
async def list_batch_schedules(
    service_id: uuid.UUID, merchant: CurrentMerchant, db: DatabaseSession
) -> list[BatchSchedule]:
    await scoped_service(service_id, merchant.id, db)
    return list(
        await db.scalars(
            select(BatchSchedule)
            .where(
                BatchSchedule.service_id == service_id,
                BatchSchedule.merchant_id == merchant.id,
            )
            .order_by(BatchSchedule.day_of_week, BatchSchedule.start_time)
        )
    )


@router.post(
    "/services/{service_id}/batch-schedules",
    response_model=BatchScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch_schedule(
    service_id: uuid.UUID,
    payload: BatchScheduleCreate,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> BatchSchedule:
    service = await scoped_service(service_id, merchant.id, db)
    if service.booking_mode != BookingMode.BATCH:
        raise AppError("VALIDATION_ERROR", "Batch schedules require a BATCH service", 400)
    schedule = BatchSchedule(
        merchant_id=merchant.id,
        service_id=service.id,
        **payload.model_dump(),
    )
    db.add(schedule)
    await commit_or_conflict(db, "An identical batch schedule already exists")
    await db.refresh(schedule)
    return schedule


@router.patch(
    "/services/{service_id}/batch-schedules/{schedule_id}",
    response_model=BatchScheduleOut,
)
async def update_batch_schedule(
    service_id: uuid.UUID,
    schedule_id: uuid.UUID,
    payload: BatchScheduleUpdate,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> BatchSchedule:
    schedule = await scoped_batch_schedule(service_id, schedule_id, merchant.id, db)
    merged = BatchScheduleCreate(
        day_of_week=(
            payload.day_of_week if payload.day_of_week is not None else schedule.day_of_week
        ),
        start_time=payload.start_time or schedule.start_time,
        end_time=payload.end_time or schedule.end_time,
        max_capacity=(
            payload.max_capacity if payload.max_capacity is not None else schedule.max_capacity
        ),
        is_active=payload.is_active if payload.is_active is not None else schedule.is_active,
    )
    for key, value in merged.model_dump().items():
        setattr(schedule, key, value)
    await commit_or_conflict(db, "An identical batch schedule already exists")
    await db.refresh(schedule)
    return schedule


@router.delete(
    "/services/{service_id}/batch-schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_batch_schedule(
    service_id: uuid.UUID,
    schedule_id: uuid.UUID,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> Response:
    schedule = await scoped_batch_schedule(service_id, schedule_id, merchant.id, db)
    schedule.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
