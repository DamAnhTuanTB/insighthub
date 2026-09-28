"""Authenticated Slack Events ingress; long work is always queued."""

from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from .audit import AuditLogger
from .config import Settings
from .queueing import EventQueue, MemoryEventQueue, RedisEventQueue
from .security import SignatureError, verify_slack_signature


def _request_id(body: bytes) -> str:
    return "request-" + hashlib.sha256(body).hexdigest()[:16]


def create_app(
    settings: Settings | None = None,
    queue: EventQueue | None = None,
    audit: AuditLogger | None = None,
) -> FastAPI:
    configured = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        created_queue = queue
        if created_queue is None:
            created_queue = (
                MemoryEventQueue()
                if configured.queue_mode == "memory"
                else await RedisEventQueue.connect(configured.redis_url)
            )
        application.state.event_queue = created_queue
        application.state.audit = audit or AuditLogger()
        yield
        if queue is None:
            await created_queue.close()

    application = FastAPI(title="InsightHub ChatOps", version="1.0.0", lifespan=lifespan)

    @application.get("/healthz")
    async def health() -> dict[str, Any]:
        return {
            "status": "ready" if configured.ingress_ready else "not_ready",
            "ready": configured.ingress_ready,
            "transport": "http",
            "queue": configured.queue_mode,
            "tool_mode": configured.tool_mode,
        }

    @application.post("/slack/events")
    async def slack_events(request: Request) -> dict[str, Any]:
        body = await request.body()
        request_event_id = _request_id(body)
        audit_logger: AuditLogger = request.app.state.audit
        try:
            verify_slack_signature(
                secret=configured.signing_secret,
                timestamp=request.headers.get("X-Slack-Request-Timestamp"),
                signature=request.headers.get("X-Slack-Signature"),
                body=body,
                tolerance_seconds=configured.signature_tolerance_seconds,
            )
        except SignatureError as exc:
            audit_logger.record(
                event_id=request_event_id,
                action="slack_request",
                user="unknown",
                decision="denied",
                error_code=exc.code,
            )
            raise HTTPException(status_code=401, detail="request authentication failed") from exc

        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="invalid event payload")

        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge")
            if not isinstance(challenge, str) or not challenge:
                raise HTTPException(status_code=400, detail="invalid challenge")
            audit_logger.record(
                event_id=request_event_id,
                action="slack_url_verification",
                user="slack",
                decision="allowed",
            )
            return {"challenge": challenge}

        if payload.get("type") != "event_callback":
            raise HTTPException(status_code=400, detail="unsupported event type")
        event_id = payload.get("event_id")
        event = payload.get("event")
        if not isinstance(event_id, str) or not event_id or not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="invalid event callback")

        user = event.get("user") if isinstance(event.get("user"), str) else "unknown"
        if event.get("type") != "app_mention":
            audit_logger.record(
                event_id=event_id,
                action="ignore_event_type",
                user=user,
                decision="denied",
                error_code="EVENT_TYPE_NOT_ALLOWED",
            )
            return {"ok": True, "ignored": True}
        if event.get("bot_id") or event.get("subtype") == "bot_message" or (
            configured.bot_user_id and user == configured.bot_user_id
        ):
            audit_logger.record(
                event_id=event_id,
                action="ignore_bot_event",
                user=user,
                decision="denied",
                error_code="SELF_EVENT",
            )
            return {"ok": True, "ignored": True}

        event_queue: EventQueue = request.app.state.event_queue
        queued = await event_queue.enqueue(event_id, payload)
        audit_logger.record(
            event_id=event_id,
            action="enqueue_slack_event",
            user=user,
            decision="allowed" if queued else "denied",
            tool="arq.enqueue_job",
            result="queued" if queued else "duplicate",
            error_code=None if queued else "DUPLICATE_EVENT",
        )
        return {"ok": True, "queued": queued, "duplicate": not queued}

    return application


app = create_app()
