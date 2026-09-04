import uuid
from datetime import timedelta

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.clock import Clock, utc_now
from app.core.config import get_settings
from app.core.exceptions import AppError

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def _jwt_secret() -> str:
    secret_value = get_settings().jwt_secret_key
    if secret_value is None or len(secret_value.get_secret_value()) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")
    return secret_value.get_secret_value()


def create_access_token(merchant_id: uuid.UUID, clock: Clock = utc_now) -> str:
    settings = get_settings()
    now = clock()
    payload = {
        "sub": str(merchant_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")
        return uuid.UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise AppError(
            "AUTHENTICATION_REQUIRED", "A valid access token is required", 401
        ) from exc

