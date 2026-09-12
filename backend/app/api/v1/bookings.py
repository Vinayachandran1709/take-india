from fastapi import APIRouter, status

from app.api.dependencies import CurrentClock, DatabaseSession
from app.schemas.api import BookingInitiateRequest, BookingInitiateResponse
from app.services.booking_service import initiate_booking
from app.services.payments.security import new_public_token

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post(
    "/initiate",
    response_model=BookingInitiateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking_hold(
    payload: BookingInitiateRequest,
    db: DatabaseSession,
    clock: CurrentClock,
) -> BookingInitiateResponse:
    async with db.begin():
        booking = await initiate_booking(db, payload, clock=clock)
        token, booking.public_token_hash = new_public_token()
    return BookingInitiateResponse.model_validate(booking).model_copy(
        update={"public_booking_token": token}
    )
