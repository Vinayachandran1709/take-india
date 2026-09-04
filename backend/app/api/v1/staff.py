import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.dependencies import CurrentMerchant, DatabaseSession
from app.core.exceptions import AppError
from app.models import StaffMember
from app.schemas.api import StaffCreate, StaffOut, StaffUpdate

router = APIRouter(prefix="/staff", tags=["staff"])


async def scoped_staff(
    staff_id: uuid.UUID, merchant_id: uuid.UUID, db: DatabaseSession
) -> StaffMember:
    staff = await db.scalar(
        select(StaffMember).where(
            StaffMember.id == staff_id, StaffMember.merchant_id == merchant_id
        )
    )
    if staff is None:
        raise AppError("NOT_FOUND", "Staff member not found", 404)
    return staff


@router.get("", response_model=list[StaffOut])
async def list_staff(merchant: CurrentMerchant, db: DatabaseSession) -> list[StaffMember]:
    return list(
        await db.scalars(
            select(StaffMember)
            .where(StaffMember.merchant_id == merchant.id)
            .order_by(StaffMember.created_at, StaffMember.id)
        )
    )


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffCreate, merchant: CurrentMerchant, db: DatabaseSession
) -> StaffMember:
    staff = StaffMember(merchant_id=merchant.id, name=payload.name, is_active=True)
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    return staff


@router.patch("/{staff_id}", response_model=StaffOut)
async def update_staff(
    staff_id: uuid.UUID,
    payload: StaffUpdate,
    merchant: CurrentMerchant,
    db: DatabaseSession,
) -> StaffMember:
    staff = await scoped_staff(staff_id, merchant.id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(staff, field, value)
    await db.commit()
    await db.refresh(staff)
    return staff


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    staff_id: uuid.UUID, merchant: CurrentMerchant, db: DatabaseSession
) -> Response:
    staff = await scoped_staff(staff_id, merchant.id, db)
    staff.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

