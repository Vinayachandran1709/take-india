from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.waitlist_rate_limit import check_waitlist_rate_limit
from app.models.waitlist import WaitlistEntry
from app.schemas.waitlist import WaitlistAccepted, WaitlistRequest

MAX_BODY_BYTES = 4096
UNAVAILABLE_MESSAGE = "We couldn't save your request. Please try again shortly."


class WaitlistRoute(APIRoute):
    """Bound the streamed body before FastAPI parses it, only for this endpoint."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded_handler(request: Request) -> Response:
            media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
            if media_type != "application/json":
                raise AppError("UNSUPPORTED_MEDIA_TYPE", "Send your request as JSON.", 415)
            length = request.headers.get("content-length")
            if length is not None:
                if not length.isascii() or not length.isdecimal():
                    raise AppError("INVALID_REQUEST", "Invalid request size.", 400)
                if len(length) > 10 or int(length) > MAX_BODY_BYTES:
                    raise AppError("REQUEST_TOO_LARGE", "Your request is too large.", 413)
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    raise AppError("REQUEST_TOO_LARGE", "Your request is too large.", 413)
                body.extend(chunk)

            async def receive() -> dict:
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await check_waitlist_rate_limit(request)
            try:
                return await handler(Request(request.scope, receive))
            except RequestValidationError as exc:
                # Return field guidance, never the rejected values or Pydantic input details.
                messages = {
                    "whatsapp": "Enter a valid Indian mobile number, optionally prefixed with +91.",
                    "business_type": "Choose one of the listed business types.",
                    "consent": "Agree to receive typein early-access updates on WhatsApp.",
                }
                details = [
                    {
                        "field": (
                            str(error["loc"][-1]) if error["loc"][-1] in messages else "body"
                        ),
                        "message": messages.get(
                            error["loc"][-1],
                            "Use only business_type and whatsapp in a JSON object.",
                        ),
                    }
                    for error in exc.errors()
                ]
                raise AppError(
                    "VALIDATION_ERROR",
                    "Check your business type, WhatsApp number and contact consent.",
                    400,
                    details,
                ) from None

        return bounded_handler


async def waitlist_database() -> AsyncIterator[AsyncSession]:
    """Reuse the shared session without exposing its missing-configuration exception."""
    sessions = get_db()
    try:
        try:
            session = await anext(sessions)
        except (RuntimeError, SQLAlchemyError, OSError):
            raise AppError("WAITLIST_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503) from None
        yield session
    finally:
        try:
            await sessions.aclose()
        except (SQLAlchemyError, OSError):
            raise AppError("WAITLIST_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503) from None


WaitlistDatabase = Annotated[AsyncSession, Depends(waitlist_database)]
router = APIRouter(prefix="/waitlist", tags=["waitlist"], route_class=WaitlistRoute)


@router.post("", response_model=WaitlistAccepted)
async def register_waitlist(
    payload: WaitlistRequest, db: WaitlistDatabase, response: Response
) -> WaitlistAccepted:
    response.headers["Cache-Control"] = "no-store"
    statement = (
        insert(WaitlistEntry)
        .values(whatsapp=payload.whatsapp, business_type=payload.business_type)
        .on_conflict_do_nothing(index_elements=[WaitlistEntry.whatsapp])
    )
    try:
        await db.execute(statement)
        await db.commit()
    except (SQLAlchemyError, OSError):
        try:
            await db.rollback()
        except (SQLAlchemyError, OSError):
            pass
        raise AppError("WAITLIST_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503) from None
    # New and existing registrations have the same response; existing details are not overwritten.
    return WaitlistAccepted()
