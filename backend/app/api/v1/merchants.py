from fastapi import APIRouter

from app.api.dependencies import CurrentMerchant, DatabaseSession
from app.models import Merchant
from app.schemas.api import MerchantOut, MerchantUpdate

router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.get("/me", response_model=MerchantOut)
async def get_merchant(merchant: CurrentMerchant) -> Merchant:
    return merchant


@router.patch("/me", response_model=MerchantOut)
async def update_merchant(
    payload: MerchantUpdate, merchant: CurrentMerchant, db: DatabaseSession
) -> Merchant:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(merchant, field, value)
    await db.commit()
    await db.refresh(merchant)
    return merchant

