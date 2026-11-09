from fastapi import APIRouter, Depends

from app.api.dependencies import (
    CurrentClock,
    CurrentMerchant,
    DatabaseSession,
    require_billing_access,
)
from app.models import Merchant
from app.schemas.api import MerchantOut, MerchantUpdate
from app.services.billing_service import billing_summary

router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.get("/me", response_model=MerchantOut)
async def get_merchant(merchant: CurrentMerchant, clock: CurrentClock) -> MerchantOut:
    return MerchantOut.model_validate(merchant).model_copy(
        update={"billing": billing_summary(merchant, clock())}
    )


@router.patch("/me", response_model=MerchantOut, dependencies=[Depends(require_billing_access)])
async def update_merchant(
    payload: MerchantUpdate, merchant: CurrentMerchant, db: DatabaseSession
) -> Merchant:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(merchant, field, value)
    await db.commit()
    await db.refresh(merchant)
    return merchant

