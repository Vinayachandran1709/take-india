"""Send one manually requested test email through Resend."""

import argparse
import asyncio
import logging

from app.core.config import get_settings
from app.services.email_service import get_last_response_details, send_email


async def main() -> int:
    parser = argparse.ArgumentParser(description="Send one Typein test email")
    parser.add_argument("--to", required=True, help="Destination email address")
    args = parser.parse_args()

    try:
        settings = get_settings()
    except Exception:
        print("result=False")
        return 2

    missing = []
    if not settings.resend_api_key or not settings.resend_api_key.get_secret_value():
        missing.append("RESEND_API_KEY")
    if not settings.email_from or not settings.email_from.strip():
        missing.append("EMAIL_FROM")
    if missing:
        print("result=False")
        print("missing=" + ",".join(missing))
        return 2

    # The CLI reports only the result and safe response metadata.
    service_logger = logging.getLogger("app.services.email_service")
    service_logger.addHandler(logging.NullHandler())
    service_logger.propagate = False
    success = await send_email(
        to=args.to,
        subject="Typein email test",
        html="<p>Typein email test</p>",
        text="Typein email test",
    )
    status_code, message_id = get_last_response_details()
    print(f"result={success}")
    if status_code is not None:
        print(f"status={status_code}")
    if message_id is not None:
        print(f"id={message_id}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
