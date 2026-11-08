"""V1 booking submission without the payment checkout flow."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Response, status
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentClock, DatabaseSession
from app.core.management_token import new_management_token
from app.models import Customer, Merchant, Service
from app.schemas.api import BookingInitiateRequest, BookingInitiateResponse
from app.services.booking_service import confirm_booking_without_payment
from app.services.whatsapp_service import send_booking_confirmation

router = APIRouter(prefix="/bookings", tags=["bookings"])
logger = logging.getLogger(__name__)


async def get_notification_details(
    db: AsyncSession, service_id: UUID, merchant_id: UUID, customer_id: UUID
) -> tuple[str, str, str] | None:
    """Fetch the service, merchant, and customer from the same tenant."""
    result = await db.execute(
        select(Service.title, Merchant.business_name, Customer.phone_number)
        .select_from(Service)
        .join(Merchant, Merchant.id == Service.merchant_id)
        .join(
            Customer,
            and_(Customer.id == customer_id, Customer.merchant_id == Merchant.id),
        )
        .where(Service.id == service_id, Service.merchant_id == merchant_id)
    )
    row = result.one_or_none()
    return tuple(row) if row is not None else None


@router.post(
    "/initiate",
    response_model=BookingInitiateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_confirmed_booking(
    payload: BookingInitiateRequest,
    db: DatabaseSession,
    clock: CurrentClock,
    response: Response,
    background_tasks: BackgroundTasks,
) -> BookingInitiateResponse:
    response.headers["Cache-Control"] = "no-store"
    async with db.begin():
        booking = await confirm_booking_without_payment(db, payload, clock=clock)
        token, booking.management_token_hash = new_management_token()
    booking_response = BookingInitiateResponse.model_validate(booking).model_copy(
        update={"management_token": token}
    )
    try:
        details = await get_notification_details(
            db, booking.service_id, booking.merchant_id, booking.customer_id
        )
    except SQLAlchemyError:
        logger.warning("WhatsApp confirmation details unavailable after booking commit")
        details = None

    if details is not None:
        service_title, business_name, phone_number = details
        datetime_str = datetime.combine(booking.booking_date, booking.start_time).strftime(
            "%d %b %Y, %I:%M %p"
        )
        manage_url = f"https://typein.co/manage/{token}"
        background_tasks.add_task(
            send_booking_confirmation,
            phone_number,
            service_title,
            business_name,
            datetime_str,
            manage_url,
        )
    else:
        logger.warning("WhatsApp confirmation skipped: booking details were not found")

    return booking_response
