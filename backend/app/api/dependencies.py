from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, utc_now
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.models import Merchant
from app.services.billing_service import billing_summary

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


def get_clock() -> Clock:
    return utc_now


CurrentClock = Annotated[Clock, Depends(get_clock)]


async def get_current_merchant(
    token: Annotated[str, Depends(oauth2_scheme)], db: DatabaseSession
) -> Merchant:
    merchant_id = decode_access_token(token)
    merchant = await db.scalar(
        select(Merchant).where(Merchant.id == merchant_id, Merchant.is_active.is_(True))
    )
    if merchant is None:
        raise AppError("AUTHENTICATION_REQUIRED", "Merchant account is unavailable", 401)
    return merchant


CurrentMerchant = Annotated[Merchant, Depends(get_current_merchant)]


async def require_billing_access(merchant: CurrentMerchant, clock: CurrentClock) -> None:
    if billing_summary(merchant, clock())["locked"]:
        raise AppError(
            "subscription_required",
            "A subscription is required to use this feature",
            403,
        )
