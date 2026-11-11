"""Verified, durable Meta webhook intake without customer-message side effects."""

import hashlib
import hmac
import json
import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.core.exceptions import AppError

router = APIRouter(prefix="/webhooks/meta", tags=["Meta webhooks"])
logger = logging.getLogger(__name__)
_SIGNATURE_PATTERN = re.compile(r"sha256=[0-9a-f]{64}\Z")
_MAX_BODY_BYTES = 262_144


@router.get("")
async def verify_subscription(request: Request) -> PlainTextResponse:
    token = get_settings().meta_webhook_verify_token
    if token is None:
        raise AppError("META_UNAVAILABLE", "Meta webhook is not configured", 503)
    query = request.query_params
    supplied = query.get("hub.verify_token", "")
    challenge = query.get("hub.challenge", "")
    if (
        query.get("hub.mode") != "subscribe"
        or not supplied
        or not hmac.compare_digest(token.get_secret_value(), supplied)
        or not challenge
        or len(challenge) > 256
    ):
        raise AppError("META_VERIFICATION_INVALID", "Webhook verification failed", 403)
    return PlainTextResponse(challenge, headers={"Cache-Control": "no-store"})


@router.post("")
async def receive_event(request: Request, db: DatabaseSession) -> dict[str, str]:
    app_secret = get_settings().meta_app_secret
    if app_secret is None:
        raise AppError("META_UNAVAILABLE", "Meta webhook is not configured", 503)
    signature = request.headers.get("x-hub-signature-256", "")
    if _SIGNATURE_PATTERN.fullmatch(signature) is None:
        raise AppError("META_SIGNATURE_INVALID", "Webhook signature is invalid", 401)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > _MAX_BODY_BYTES:
            raise AppError("META_PAYLOAD_TOO_LARGE", "Webhook payload is too large", 413)
    expected = "sha256=" + hmac.new(
        app_secret.get_secret_value().encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise AppError("META_SIGNATURE_INVALID", "Webhook signature is invalid", 401)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("META_PAYLOAD_INVALID", "Webhook payload is invalid", 400) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("object"), str):
        raise AppError("META_PAYLOAD_INVALID", "Webhook payload is invalid", 400)
    object_type = payload["object"]
    if len(object_type) > 80:
        raise AppError("META_PAYLOAD_INVALID", "Webhook payload is invalid", 400)
    digest = hashlib.sha256(body).hexdigest()
    try:
        result = await db.execute(
            text(
                "INSERT INTO meta_webhook_events "
                "(body_sha256, object_type, processing_status) "
                "VALUES (:digest, :object_type, 'received') "
                "ON CONFLICT (body_sha256) DO NOTHING RETURNING body_sha256"
            ),
            {"digest": digest, "object_type": object_type},
        )
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("Meta webhook persistence failed: %s", type(exc).__name__)
        raise AppError("META_UNAVAILABLE", "Webhook could not be recorded", 503) from exc
    return {"status": "received" if result.scalar_one_or_none() else "duplicate"}
