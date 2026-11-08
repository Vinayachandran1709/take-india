"""Opaque customer booking-management bearer tokens."""

import hashlib
import secrets


def new_management_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    return token, digest
