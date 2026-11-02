"""Public waitlist-only ASGI app for a dedicated backend service."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.waitlist import router as waitlist_router
from app.core.config import get_settings
from app.core.exceptions import install_exception_handlers

app = FastAPI(title="typein waitlist API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
install_exception_handlers(app)
app.include_router(waitlist_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
