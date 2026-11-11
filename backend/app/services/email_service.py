"""Minimal Resend email sender."""

import logging
from contextvars import ContextVar

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_last_response: ContextVar[tuple[int | None, str | None]] = ContextVar(
    "email_last_response", default=(None, None)
)


def get_last_response_details() -> tuple[int | None, str | None]:
    """Return status and message ID from the last send in this async context."""
    return _last_response.get()


async def send_email(
    to: str, subject: str, html: str, text: str | None = None,
    *, idempotency_key: str | None = None,
) -> bool:
    """Send one email; never raise an HTTP or transport error to the caller."""
    _last_response.set((None, None))
    settings = get_settings()
    api_key = settings.resend_api_key.get_secret_value() if settings.resend_api_key else None
    if not api_key or not settings.email_from or not settings.email_from.strip():
        logger.warning("Resend email skipped: RESEND_API_KEY or EMAIL_FROM is missing")
        return False

    payload = {
        "from": settings.email_from,
        "to": to,
        "subject": subject,
        "html": html,
    }
    if text is not None:
        payload["text"] = text

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {api_key}"}
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            response = await client.post(
                "https://api.resend.com/emails",
                headers=headers,
                json=payload,
            )
    except httpx.RequestError as exc:
        logger.warning("Resend email failed: status=none error=%s", type(exc).__name__)
        return False

    _last_response.set((response.status_code, None))
    if not response.is_success:
        logger.warning("Resend email failed: status=%s error=HTTPStatusError", response.status_code)
        return False

    try:
        data = response.json()
    except ValueError:
        data = None
    message_id = data.get("id") if isinstance(data, dict) else None
    if isinstance(message_id, str):
        _last_response.set((response.status_code, message_id))
    logger.info("Resend email accepted: status=%s", response.status_code)
    return True
