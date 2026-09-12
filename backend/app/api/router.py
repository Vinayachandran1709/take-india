from fastapi import APIRouter

from app.api.v1 import auth, bookings, merchants, payments, schedules, services, staff, storefront

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(merchants.router)
api_router.include_router(services.router)
api_router.include_router(staff.router)
api_router.include_router(schedules.router)
api_router.include_router(storefront.router)
api_router.include_router(bookings.router)
api_router.include_router(payments.router)
