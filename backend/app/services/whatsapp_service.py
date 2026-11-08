"""Send V1 booking updates through the WhatsApp Cloud API."""

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_booking_confirmation(
    phone_number: str,
    service_title: str,
    business_name: str,
    datetime_str: str,
    manage_url: str,
) -> None:
    await _send_template(
        "booking_confirmation_v1",
        phone_number,
        service_title,
        business_name,
        datetime_str,
        manage_url,
    )


async def send_reschedule_confirmation(
    phone_number: str,
    service_title: str,
    business_name: str,
    new_datetime_str: str,
    manage_url: str,
) -> None:
    await _send_template(
        "reschedule_confirmation_v1",
        phone_number,
        service_title,
        business_name,
        new_datetime_str,
        manage_url,
    )


async def _send_template(
    template_name: str,
    phone_number: str,
    service_title: str,
    business_name: str,
    datetime_str: str,
    manage_url: str,
) -> None:
    settings = get_settings()
    if not settings.whatsapp_phone_number_id or not settings.whatsapp_api_token:
        logger.warning("WhatsApp %s skipped: sender credentials are not configured", template_name)
        return

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number.lstrip("+"),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": service_title},
                        {"type": "text", "text": business_name},
                        {"type": "text", "text": datetime_str},
                        {"type": "text", "text": manage_url},
                    ],
                }
            ],
        },
    }
    url = (
        f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            result = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_api_token.get_secret_value()}",
                },
                json=payload,
            )
    except httpx.RequestError as exc:
        logger.warning("WhatsApp %s request failed: %s", template_name, type(exc).__name__)
        return

    logger.info("WhatsApp %s API status=%s", template_name, result.status_code)
    if result.is_error:
        logger.warning("WhatsApp %s was not accepted by Meta", template_name)
