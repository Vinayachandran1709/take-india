import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.core.phone import normalize_phone_number
from app.schemas.api import ApiModel

WaitlistBusinessType = Literal[
    "Salon & hair studio",
    "Makeup, lash & nail artist",
    "Custom baker",
    "Aesthetic or dental clinic",
    "Yoga, dance or fitness studio",
    "Other",
]


class WaitlistRequest(ApiModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    business_type: WaitlistBusinessType
    whatsapp: str = Field(min_length=10, max_length=32)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("business_type", mode="before")
    @classmethod
    def trim_business_type(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("whatsapp")
    @classmethod
    def normalize_whatsapp(cls, value: str) -> str:
        compact = re.sub(r"[\s()-]", "", value)
        if not re.fullmatch(r"(?:\+91)?[6-9][0-9]{9}", compact):
            raise ValueError("Enter a valid Indian mobile number, optionally prefixed with +91")
        return normalize_phone_number(compact)


class WaitlistAccepted(ApiModel):
    accepted: Literal[True] = True
