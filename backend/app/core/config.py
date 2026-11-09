import os
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str | None = None
    direct_database_url: str | None = None
    test_database_url: str | None = None
    allow_test_database_reset: bool = False
    credential_encryption_key: SecretStr | None = None
    public_api_url: str = "http://localhost:8000"
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    whatsapp_api_token: SecretStr | None = None
    whatsapp_api_version: str = "v26.0"
    resend_api_key: SecretStr | None = None
    email_from: str | None = None

    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    app_timezone: str = "Asia/Kolkata"
    booking_hold_minutes: int = Field(default=10, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("app_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("APP_TIMEZONE must be a valid IANA timezone") from exc
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=os.environ.get("TAKE_INDIA_ENV_FILE", ".env"))
