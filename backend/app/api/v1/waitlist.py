import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.waitlist_rate_limit import check_waitlist_rate_limit
from app.models.waitlist import WaitlistEntry
from app.schemas.waitlist import WaitlistAccepted, WaitlistRequest

MAX_BODY_BYTES = 4096
UNAVAILABLE_MESSAGE = "We couldn't save your request. Please try again shortly."
logger = logging.getLogger(__name__)


def log_database_failure(stage: str, exc: Exception) -> None:
    """Record error classes only; never include submitted values or a database URL."""
    cause = exc.__cause__ or exc.__context__
    original = getattr(exc, "orig", None)
    logger.warning(
        "Waitlist database failure stage=%s error=%s cause=%s original=%s",
        stage,
        type(exc).__name__,
        type(cause).__name__ if cause else "none",
        type(original).__name__ if original else "none",
    )


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
                    "name": "Enter your name (up to 120 characters).",
                    "whatsapp": "Enter a valid Indian mobile number, optionally prefixed with +91.",
                    "business_type": "Choose one of the listed business types.",
                }
                details = [
                    {
                        "field": (
                            str(error["loc"][-1]) if error["loc"][-1] in messages else "body"
                        ),
                        "message": messages.get(
                            error["loc"][-1],
                            "Use only name, business_type and whatsapp in a JSON object.",
                        ),
                    }
                    for error in exc.errors()
                ]
                raise AppError(
                    "VALIDATION_ERROR",
                    "Check your name, business type and WhatsApp number.",
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
        except Exception as exc:
            # Connection setup can raise an unwrapped driver error before SQLAlchemy
            # converts it. Keep database diagnostics out of public responses.
            log_database_failure("open", exc)
            raise AppError("WAITLIST_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503) from None
        yield session
    finally:
        try:
            await sessions.aclose()
        except Exception as exc:
            log_database_failure("close", exc)
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
        .values(name=payload.name, whatsapp=payload.whatsapp, business_type=payload.business_type)
        .on_conflict_do_update(
            index_elements=[WaitlistEntry.whatsapp],
            set_={"name": payload.name},
            where=WaitlistEntry.name.is_(None),
        )
    )
    try:
        await db.execute(statement)
        await db.commit()
    except Exception as exc:
        log_database_failure("write", exc)
        try:
            await db.rollback()
        except Exception:
            pass
        raise AppError("WAITLIST_UNAVAILABLE", UNAVAILABLE_MESSAGE, 503) from None
    # Retried legacy entries can gain a missing name. Other fields stay unchanged.
    return WaitlistAccepted()
