from fastapi import APIRouter, status

from app.api.dependencies import CurrentClock, DatabaseSession
from app.schemas.api import BookingInitiateRequest, BookingInitiateResponse
from app.services.booking_service import initiate_booking

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
    return BookingInitiateResponse.model_validate(booking)
