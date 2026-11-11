from datetime import timedelta

from fastapi import APIRouter, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentClock, CurrentMerchant, DatabaseSession
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Merchant
from app.schemas.api import AuthResponse, LoginRequest, MerchantOut, SignupRequest
from app.schemas.billing import BillingSummary
from app.services.billing_service import billing_summary

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: DatabaseSession, clock: CurrentClock) -> AuthResponse:
    existing = await db.scalar(
        select(Merchant.id).where(
            or_(Merchant.email == str(payload.email), Merchant.slug == payload.slug)
        )
    )
    if existing is not None:
        raise AppError("RESOURCE_CONFLICT", "Email or storefront slug is already in use", 409)

    merchant = Merchant(
        business_name=payload.business_name,
        slug=payload.slug,
        business_type=payload.business_type,
        owner_name=payload.owner_name,
        phone_number=payload.phone_number,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        timezone=payload.timezone,
        is_active=True,
        trial_ends_at=clock() + timedelta(days=get_settings().billing_trial_days),
    )
    db.add(merchant)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            "RESOURCE_CONFLICT", "Email or storefront slug is already in use", 409
        ) from exc
    await db.refresh(merchant)
    return AuthResponse(
        access_token=create_access_token(merchant.id),
        merchant=MerchantOut.model_validate(merchant).model_copy(
            update={"billing": BillingSummary.model_validate(billing_summary(merchant, clock()))}
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: DatabaseSession) -> AuthResponse:
    merchant = await db.scalar(select(Merchant).where(Merchant.email == str(payload.email)))
    if merchant is None or not verify_password(payload.password, merchant.password_hash):
        raise AppError("AUTHENTICATION_REQUIRED", "Email or password is incorrect", 401)
    if not merchant.is_active:
        raise AppError("FORBIDDEN", "Merchant account is inactive", 403)
    return AuthResponse(
        access_token=create_access_token(merchant.id),
        merchant=MerchantOut.model_validate(merchant),
    )


@router.get("/me", response_model=MerchantOut)
async def auth_me(merchant: CurrentMerchant, clock: CurrentClock) -> MerchantOut:
    return MerchantOut.model_validate(merchant).model_copy(
        update={"billing": BillingSummary.model_validate(billing_summary(merchant, clock()))}
    )
