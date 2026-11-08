from fastapi import APIRouter

from app.api.v1 import (
    agenda,
    auth,
    bookings,
    manage,
    merchants,
    payments,
    schedules,
    services,
    staff,
    storefront,
    waitlist,
)

api_router = APIRouter()
api_router.include_router(agenda.router)
api_router.include_router(auth.router)
api_router.include_router(merchants.router)
api_router.include_router(services.router)
api_router.include_router(staff.router)
api_router.include_router(schedules.router)
api_router.include_router(storefront.router)
api_router.include_router(bookings.router)
api_router.include_router(manage.router)
api_router.include_router(payments.router)
api_router.include_router(waitlist.router)
