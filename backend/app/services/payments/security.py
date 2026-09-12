import hashlib
import hmac
import secrets
from decimal import Decimal

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import AppError


def cipher() -> Fernet:
    key = get_settings().credential_encryption_key
    try:
        if key is None:
            raise ValueError
        return Fernet(key.get_secret_value().encode())
    except (ValueError, TypeError):
        raise AppError(
            "PAYMENT_CONFIGURATION_INVALID",
            "Credential encryption is unavailable",
            503,
        ) from None


def encrypt(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken:
        raise AppError(
            "PAYMENT_CONFIGURATION_INVALID",
            "Credentials cannot be decrypted",
            503,
        ) from None


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_public_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def valid_token(value: str, stored: str | None) -> bool:
    return bool(stored) and hmac.compare_digest(token_hash(value), stored or "")


def verify_signature(body: bytes, signature: str, secret: str, code: str) -> None:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), signature.encode()):
        raise AppError(code, "Payment signature is invalid", 400)


def to_paise(amount: Decimal) -> int:
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise AppError("PAYMENT_AMOUNT_INVALID", "Invalid payment amount", 400)
    value = amount * 100
    if value != value.to_integral_value():
        raise AppError("PAYMENT_AMOUNT_INVALID", "Amount has excess precision", 400)
    return int(value)
