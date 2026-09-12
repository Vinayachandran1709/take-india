import base64
import hashlib
import hmac
import uuid
from decimal import Decimal

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.api.v1.payments import PaymentSettingsInput
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.test_safety import assert_test_database_safe
from app.services.payments.gateway import (
    AmbiguousOrder,
    RazorpayGateway,
    receipt_for,
    validate_amount,
)
from app.services.payments.security import (
    decrypt,
    encrypt,
    new_public_token,
    to_paise,
    valid_token,
    verify_signature,
)
from app.services.payments.webhooks import dedupe_key, safe_failure


def test_token_randomness_hashing_and_concealment():
    token, digest = new_public_token()
    assert len(base64.urlsafe_b64decode(token + "=")) == 32
    assert len(digest) == 64 and token not in digest
    assert valid_token(token, digest)
    assert not valid_token(token + "x", digest)
    assert not valid_token(token, None)
    assert new_public_token()[0] != token


def test_encryption_randomized_roundtrip_and_wrong_key(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    secret = "a-secret-that-must-not-be-stored"
    ciphertext = encrypt(secret)
    assert ciphertext != encrypt(secret) and secret not in ciphertext
    assert decrypt(ciphertext) == secret
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with pytest.raises(AppError, match="cannot be decrypted"):
        decrypt(ciphertext)
    get_settings.cache_clear()


@pytest.mark.parametrize("mode,key", [("LIVE", "rzp_live_123"), ("TEST", "rzp_live_123")])
def test_live_settings_rejected(mode, key):
    with pytest.raises(ValidationError):
        PaymentSettingsInput(
            mode=mode, key_id=key, key_secret="secret123", webhook_secret="secret1234567890"
        )


def test_receipt_and_minimum_are_separate_from_conversion():
    identifier = uuid.uuid4()
    receipt = receipt_for(identifier)
    assert receipt == receipt_for(identifier)
    assert receipt != receipt_for(uuid.uuid4())
    assert receipt.isascii() and len(receipt) == 35
    assert to_paise(Decimal("0.01")) == 1
    assert validate_amount(Decimal("1.00")) == 100
    with pytest.raises(AppError) as error:
        validate_amount(Decimal("0.99"))
    assert error.value.code == "PAYMENT_AMOUNT_INVALID"


def test_raw_signature_and_event_id_precedence():
    raw = b'{ "event": "payment.captured" }'
    signature = hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    verify_signature(raw, signature, "secret", "INVALID")
    with pytest.raises(AppError):
        verify_signature(raw.replace(b" ", b""), signature, "secret", "INVALID")
    config_id = uuid.uuid4()
    assert dedupe_key(config_id, "ev1", {"event": "a"}) == dedupe_key(
        config_id, "ev1", {"event": "b"}
    )
    assert dedupe_key(config_id, "ev1", {}) != dedupe_key(config_id, "ev2", {})
    assert dedupe_key(config_id, None, {"event": "a"}) == dedupe_key(
        config_id, None, {"event": "a"}
    )
    assert dedupe_key(uuid.uuid4(), "ev1", {}) != dedupe_key(config_id, "ev1", {})
    assert safe_failure("BAD_REQUEST_ERROR") == "BAD_REQUEST_ERROR"
    assert safe_failure("Customer vinay@example.com failed") is None
    assert dedupe_key(config_id, None, {"event": "ignored", "payload": None})


def test_pooler_and_direct_test_database_aliases_rejected():
    settings = Settings(
        _env_file=None,
        environment="test",
        allow_test_database_reset=True,
        database_url="postgresql://user:secret@ep-same-pooler.neon.tech/neondb",
        direct_database_url=None,
        test_database_url="postgresql://another:password@ep-same.neon.tech/neondb?sslmode=require",
    )
    with pytest.raises(RuntimeError, match="must differ"):
        assert_test_database_safe(settings)


async def test_gateway_minimum_makes_no_request_and_timeout_never_retries():
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret-bearing-provider-detail", request=request)

    gateway = RazorpayGateway(httpx.MockTransport(timeout))
    with pytest.raises(AppError) as error:
        await gateway.create_order("rzp_test_123", "secret", Decimal("0.01"), "INR", "TI_test")
    assert error.value.code == "PAYMENT_AMOUNT_INVALID" and not calls
    with pytest.raises(AmbiguousOrder) as error:
        await gateway.create_order("rzp_test_123", "secret", Decimal("1.00"), "INR", "TI_test")
    assert len(calls) == 1 and "secret-bearing" not in str(error.value)


def test_local_phase2_guard_rejects_phase1_and_test_aliases(tmp_path, monkeypatch):
    from scripts.phase2 import phase2_environment

    monkeypatch.chdir(tmp_path)
    key = Fernet.generate_key().decode()
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql://a:b@ep-original-pooler.neon.tech/neondb\n"
        "TEST_DATABASE_URL=postgresql://a:b@ep-tests.neon.tech/neondb\n",
        encoding="utf-8",
    )
    for hostname in ("ep-original", "ep-tests"):
        (tmp_path / ".env.phase2").write_text(
            f"DATABASE_URL=postgresql://c:d@{hostname}-pooler.neon.tech/neondb\n"
            f"DIRECT_DATABASE_URL=postgresql://c:d@{hostname}.neon.tech/neondb\n"
            f"CREDENTIAL_ENCRYPTION_KEY={key}\nJWT_SECRET_KEY=test-secret\n",
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="separate database"):
            phase2_environment()
