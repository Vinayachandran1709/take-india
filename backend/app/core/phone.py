import phonenumbers


class InvalidPhoneNumber(ValueError):
    pass


def normalize_phone_number(value: str, default_region: str = "IN") -> str:
    raw = value.strip()
    if not raw:
        raise InvalidPhoneNumber("Phone number is required")
    try:
        parsed = phonenumbers.parse(raw, None if raw.startswith("+") else default_region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumber("Enter a valid phone number") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumber("Enter a valid phone number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

