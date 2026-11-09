"""Database-free checks for the Resend sender."""

import json
from types import SimpleNamespace

import httpx
from pydantic import SecretStr

from app.services import email_service


async def test_send_email_posts_expected_payload(monkeypatch):
    captured = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "test-message-id"})

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handle)

    def mock_client(**kwargs):
        captured["timeout"] = kwargs["timeout"]
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(email_service.httpx, "AsyncClient", mock_client)
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key=SecretStr("test-only-key"),
            email_from="Typein <sender@example.test>",
        ),
    )

    assert await email_service.send_email(
        "recipient@example.test", "Hello", "<p>Hello</p>", "Hello"
    )
    assert captured == {
        "url": "https://api.resend.com/emails",
        "authorization": "Bearer test-only-key",
        "payload": {
            "from": "Typein <sender@example.test>",
            "to": "recipient@example.test",
            "subject": "Hello",
            "html": "<p>Hello</p>",
            "text": "Hello",
        },
        "timeout": 10.0,
    }
    assert email_service.get_last_response_details() == (200, "test-message-id")


async def test_missing_key_skips_network(monkeypatch):
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(resend_api_key=None, email_from="Typein <sender@example.test>"),
    )

    def fail_if_client_created(**kwargs):
        raise AssertionError("Network client must not be created without a key")

    monkeypatch.setattr(email_service.httpx, "AsyncClient", fail_if_client_created)
    assert not await email_service.send_email("recipient@example.test", "Hello", "<p>Hello</p>")
    assert email_service.get_last_response_details() == (None, None)


async def test_non_2xx_logs_status_without_key_or_body(monkeypatch, caplog):
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, text="test-only-key confidential-response")

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        email_service.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key=SecretStr("test-only-key"),
            email_from="Typein <sender@example.test>",
        ),
    )

    assert not await email_service.send_email("recipient@example.test", "Hello", "<p>Hello</p>")
    assert email_service.get_last_response_details() == (422, None)
    assert "status=422" in caplog.text
    assert "HTTPStatusError" in caplog.text
    assert "test-only-key" not in caplog.text
    assert "confidential-response" not in caplog.text


async def test_transport_error_returns_false_without_response(monkeypatch, caplog):
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable", request=request)

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        email_service.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key=SecretStr("test-only-key"),
            email_from="Typein <sender@example.test>",
        ),
    )

    assert not await email_service.send_email("recipient@example.test", "Hello", "<p>Hello</p>")
    assert email_service.get_last_response_details() == (None, None)
    assert "ConnectError" in caplog.text
    assert "test-only-key" not in caplog.text
