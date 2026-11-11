"""V1 product ASGI app: merchant setup, storefront, and confirmed bookings."""

import asyncio
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.dependencies import require_billing_access
from app.api.v1 import (
    agenda,
    auth,
    billing,
    billing_webhooks,
    confirmed_bookings,
    manage,
    merchants,
    meta_webhooks,
    schedules,
    services,
    staff,
    storefront,
)
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import install_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

settings = get_settings()
app = FastAPI(title="typein V1 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
install_exception_handlers(app)
for router in (
    auth.router,
    agenda.router,
    merchants.router,
    services.router,
    staff.router,
    schedules.router,
    storefront.router,
    confirmed_bookings.router,
    manage.router,
    billing.router,
    billing_webhooks.router,
    meta_webhooks.router,
):
    if router in (agenda.router, services.router, staff.router, schedules.router):
        app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_billing_access)])
    else:
        app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def ready() -> dict[str, str]:
    """Check database reachability without disclosing connection details."""
    if engine is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger(__name__).warning("Database readiness failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}
