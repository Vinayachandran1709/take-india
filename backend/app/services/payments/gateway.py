"""The only Razorpay network boundary. No automatic POST retries or raw provider errors."""

from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

from app.core.exceptions import AppError
from app.services.payments.security import to_paise


class AmbiguousOrder(AppError):
    def __init__(self) -> None:
        super().__init__("PAYMENT_ORDER_UNKNOWN", "Order creation requires reconciliation", 503)


def receipt_for(transaction_id: UUID) -> str:
    return f"TI_{transaction_id.hex}"


def validate_amount(amount: Decimal, currency: str = "INR") -> int:
    paise = to_paise(amount)
    if currency != "INR" or paise < 100:
        raise AppError("PAYMENT_AMOUNT_INVALID", "Razorpay requires at least INR 1.00", 400)
    return paise


class RazorpayGateway:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def request(
        self,
        key_id: str,
        secret: str,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not key_id.startswith("rzp_test_"):
            raise AppError(
                "PAYMENT_TEST_MODE_REQUIRED", "Only Razorpay Test Mode is supported", 400
            )
        try:
            async with httpx.AsyncClient(
                base_url="https://api.razorpay.com/v1/",
                auth=httpx.BasicAuth(key_id, secret),
                timeout=httpx.Timeout(15.0, connect=5.0),
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.request(method, path, json=body, params=params)
        except httpx.TransportError:
            if method == "POST":
                raise AmbiguousOrder() from None
            raise AppError(
                "PAYMENT_PROVIDER_UNAVAILABLE", "Payment provider unavailable", 503
            ) from None
        if response.status_code >= 500 or response.status_code in (408, 429):
            if method == "POST":
                raise AmbiguousOrder()
            raise AppError("PAYMENT_PROVIDER_UNAVAILABLE", "Payment provider unavailable", 503)
        if response.status_code in (401, 403):
            raise AppError("PAYMENT_CREDENTIALS_INVALID", "Razorpay credentials were rejected", 400)
        if not response.is_success:
            raise AppError("PAYMENT_PROVIDER_REJECTED", "Razorpay rejected the request", 400)
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            if method == "POST":
                raise AmbiguousOrder() from None
            raise AppError(
                "PAYMENT_PROVIDER_UNAVAILABLE", "Invalid provider response", 503
            ) from None
        return data

    async def validate_credentials(self, key_id: str, secret: str) -> None:
        await self.request(key_id, secret, "GET", "orders", params={"count": 1})

    async def create_order(
        self,
        key_id: str,
        secret: str,
        amount: Decimal,
        currency: str,
        receipt: str,
    ) -> dict[str, Any]:
        paise = validate_amount(amount, currency)
        if not receipt.isascii() or not 1 <= len(receipt) <= 40:
            raise AppError("PAYMENT_RECEIPT_INVALID", "Invalid internal receipt", 400)
        return await self.request(
            key_id,
            secret,
            "POST",
            "orders",
            body={
                "amount": paise,
                "currency": currency,
                "receipt": receipt,
            },
        )

    async def fetch_payment(self, key_id: str, secret: str, payment_id: str) -> dict[str, Any]:
        self.validate_id(payment_id, "pay_")
        return await self.request(key_id, secret, "GET", f"payments/{payment_id}")

    async def fetch_order(self, key_id: str, secret: str, order_id: str) -> dict[str, Any]:
        self.validate_id(order_id, "order_")
        return await self.request(key_id, secret, "GET", f"orders/{order_id}")

    async def order_payments(self, key_id: str, secret: str, order_id: str) -> dict[str, Any]:
        self.validate_id(order_id, "order_")
        return await self.request(key_id, secret, "GET", f"orders/{order_id}/payments")

    async def find_order(self, key_id: str, secret: str, receipt: str) -> dict[str, Any] | None:
        data = await self.request(
            key_id,
            secret,
            "GET",
            "orders",
            params={
                "receipt": receipt,
                "count": 100,
            },
        )
        matches = [item for item in data.get("items", []) if item.get("receipt") == receipt]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def validate_id(value: str, prefix: str) -> None:
        if not (
            isinstance(value, str)
            and value.startswith(prefix)
            and value.isascii()
            and value.replace("_", "").isalnum()
            and len(value) <= 100
        ):
            raise AppError("PAYMENT_ID_INVALID", "Invalid provider identifier", 400)


def get_gateway() -> RazorpayGateway:
    return RazorpayGateway()
