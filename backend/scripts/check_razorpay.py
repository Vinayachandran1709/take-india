"""Read-only Razorpay plan diagnostic. Run manually with environment variables set.

Outputs only booleans and the key mode; never prints credentials or provider bodies.
"""

import asyncio

import httpx

from app.core.config import Settings
from app.services.billing_service import RAZORPAY_API, validate_plan


async def main() -> None:
    settings = Settings(_env_file=None)
    key = settings.razorpay_key_id or ""
    mode = "rzp_live" if key.startswith("rzp_live_") else (
        "rzp_test" if key.startswith("rzp_test_") else "unknown"
    )
    expected = "rzp_live" if settings.environment.lower() == "production" else "rzp_test"
    print(f"key_mode={mode}")
    print(f"key_present={bool(key)}")
    print(f"secret_present={bool(settings.razorpay_key_secret)}")
    print(f"plan_id_present={bool(settings.razorpay_plan_id)}")
    print(f"mode_matches_environment={mode == expected}")

    if not (mode == expected and settings.razorpay_key_secret and settings.razorpay_plan_id):
        print("plan_check_http_ok=False")
        print("plan_matches=False")
        return
    try:
        async with httpx.AsyncClient(
            auth=(key, settings.razorpay_key_secret.get_secret_value()),
            timeout=httpx.Timeout(10.0),
        ) as client:
            response = await client.get(f"{RAZORPAY_API}/plans/{settings.razorpay_plan_id}")
        print(f"plan_check_http_ok={response.is_success}")
        print(f"plan_matches={response.is_success and validate_plan(response.json(), settings)}")
    except (httpx.RequestError, ValueError):
        print("plan_check_http_ok=False")
        print("plan_matches=False")


if __name__ == "__main__":
    asyncio.run(main())
