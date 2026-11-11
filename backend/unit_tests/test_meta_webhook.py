import hashlib
import hmac
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import meta_webhooks
from app.core.database import get_db
from app.v1_main import app

_SECRET = "local-meta-test-secret"


class FakeResult:
    def __init__(self, inserted: bool) -> None:
        self.inserted = inserted

    def scalar_one_or_none(self):
        return "stored" if self.inserted else None


class FakeSession:
    def __init__(self) -> None:
        self.digests: set[str] = set()
        self.commits = 0

    async def execute(self, _statement, parameters):
        digest = parameters["digest"]
        inserted = digest not in self.digests
        self.digests.add(digest)
        return FakeResult(inserted)

    async def commit(self):
        self.commits += 1


def _signed(body: bytes) -> dict[str, str]:
    digest = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


async def test_meta_challenge_and_bad_token(monkeypatch):
    monkeypatch.setattr(
        meta_webhooks, "get_settings",
        lambda: SimpleNamespace(meta_webhook_verify_token=SecretStr("verify-test-token")),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        good = await client.get(
            "/api/v1/webhooks/meta",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-test-token",
                "hub.challenge": "123456",
            },
        )
        bad = await client.get(
            "/api/v1/webhooks/meta",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "123456",
            },
        )
    assert good.status_code == 200
    assert good.text == "123456"
    assert bad.status_code == 403
    assert "verify-test-token" not in bad.text


async def test_meta_signed_delivery_is_deduplicated(monkeypatch):
    monkeypatch.setattr(
        meta_webhooks, "get_settings", lambda: SimpleNamespace(meta_app_secret=SecretStr(_SECRET))
    )
    session = FakeSession()

    async def fake_db():
        yield session

    app.dependency_overrides[get_db] = fake_db
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            invalid = await client.post("/api/v1/webhooks/meta", content=body)
            first = await client.post("/api/v1/webhooks/meta", content=body, headers=_signed(body))
            repeat = await client.post("/api/v1/webhooks/meta", content=body, headers=_signed(body))
    finally:
        app.dependency_overrides.clear()
    assert invalid.status_code == 401
    assert first.status_code == 200 and first.json() == {"status": "received"}
    assert repeat.status_code == 200 and repeat.json() == {"status": "duplicate"}
    assert session.commits == 2
    assert len(session.digests) == 1


async def test_meta_signed_invalid_json_is_not_persisted(monkeypatch):
    monkeypatch.setattr(
        meta_webhooks, "get_settings", lambda: SimpleNamespace(meta_app_secret=SecretStr(_SECRET))
    )
    session = FakeSession()

    async def fake_db():
        yield session

    app.dependency_overrides[get_db] = fake_db
    body = b"invalid JSON"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/meta", content=body, headers=_signed(body)
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
    assert session.commits == 0


async def test_meta_database_failure_never_acknowledges_event(monkeypatch):
    monkeypatch.setattr(
        meta_webhooks, "get_settings", lambda: SimpleNamespace(meta_app_secret=SecretStr(_SECRET))
    )

    class BrokenSession:
        async def execute(self, _statement, _parameters):
            raise SQLAlchemyError("private detail")

        async def rollback(self):
            return None

    async def fake_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = fake_db
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/meta", content=body, headers=_signed(body)
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "private detail" not in response.text
