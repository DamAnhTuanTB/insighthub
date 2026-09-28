"""Day 5 behavioral contract: auth, ACK/dedup, permissions and audit."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.audit import AuditLogger
from app.config import Settings
from app.main import create_app
from app.mutation import MemoryMutationExecutor
from app.permissions import MemoryApprovalStore, PermissionDenied, PermissionEngine
from app.processor import SlackEventProcessor
from app.queueing import MemoryEventQueue, RedisEventQueue
from app.security import slack_signature
from app.slack import MemoryReplyClient
from app.tools import FixtureToolClient


SECRET = "local-test-signing-secret"


def settings() -> Settings:
    return Settings(
        signing_secret=SECRET,
        bot_token="xoxb-test-token",
        bot_user_id="B_TEST",
        redis_url="redis://127.0.0.1:6379/15",
        queue_mode="memory",
        tool_mode="fixture",
        namespace="insighthub-dev",
        repository_root=Path(os.environ.get("INSIGHTHUB_REPO_ROOT", Path(__file__).parents[3])).resolve(),
    )


def signed_headers(body: bytes, timestamp: int | None = None) -> dict[str, str]:
    request_timestamp = str(timestamp or int(time.time()))
    return {
        "X-Slack-Request-Timestamp": request_timestamp,
        "X-Slack-Signature": slack_signature(SECRET, request_timestamp, body),
        "Content-Type": "application/json",
    }


def callback(event_id: str = "Ev-1", text: str = "api healthy?") -> bytes:
    return json.dumps(
        {
            "type": "event_callback",
            "event_id": event_id,
            "event": {
                "type": "app_mention",
                "user": "U_TEST",
                "channel": "C_TEST",
                "text": text,
                "ts": "1.000",
            },
        },
        separators=(",", ":"),
    ).encode()


def test_invalid_signature() -> None:
    queue = MemoryEventQueue()
    with TestClient(create_app(settings(), queue, AuditLogger())) as client:
        response = client.post(
            "/slack/events",
            content=callback(),
            headers={
                "X-Slack-Request-Timestamp": str(int(time.time())),
                "X-Slack-Signature": "v0=invalid",
            },
        )
    assert response.status_code == 401
    assert queue.jobs == []


def test_stale_signature_rejected() -> None:
    body = callback()
    with TestClient(create_app(settings(), MemoryEventQueue(), AuditLogger())) as client:
        response = client.post("/slack/events", content=body, headers=signed_headers(body, int(time.time()) - 301))
    assert response.status_code == 401


def test_signed_challenge() -> None:
    body = json.dumps({"type": "url_verification", "challenge": "challenge-value"}).encode()
    with TestClient(create_app(settings(), MemoryEventQueue(), AuditLogger())) as client:
        response = client.post("/slack/events", content=body, headers=signed_headers(body))
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-value"}


def test_duplicate_event() -> None:
    queue = MemoryEventQueue()
    body = callback("Ev-duplicate")
    with TestClient(create_app(settings(), queue, AuditLogger())) as client:
        first = client.post("/slack/events", content=body, headers=signed_headers(body))
        second = client.post("/slack/events", content=body, headers=signed_headers(body))
    assert first.json()["queued"] is True
    assert second.json()["duplicate"] is True
    assert len(queue.jobs) == 1


def test_non_app_mention_event_is_ignored() -> None:
    queue = MemoryEventQueue()
    payload = json.loads(callback("Ev-message-event"))
    payload["event"]["type"] = "message"
    body = json.dumps(payload, separators=(",", ":")).encode()
    with TestClient(create_app(settings(), queue, AuditLogger())) as client:
        response = client.post("/slack/events", content=body, headers=signed_headers(body))
    assert response.status_code == 200
    assert response.json()["ignored"] is True
    assert queue.jobs == []


def test_redis_queue_uses_event_id_as_job_id() -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.jobs: list[tuple[str, str, str]] = []
            self.values: dict[str, str] = {}

        async def set(
            self,
            key: str,
            value: str,
            *,
            ex: int,
            nx: bool = False,
        ) -> bool:
            if nx and key in self.values:
                return False
            self.values[key] = value
            return True

        async def delete(self, *keys: str) -> None:
            for key in keys:
                self.values.pop(key, None)

        async def enqueue_job(self, function: str, event_id: str, *, _job_id: str) -> object:
            self.jobs.append((function, event_id, _job_id))
            return object()

    redis = FakeRedis()

    async def exercise() -> None:
        queue = RedisEventQueue(redis)  # type: ignore[arg-type]
        payload = {"event_id": "Ev-stable", "token": "must-not-enter-job-arguments"}
        assert await queue.enqueue("Ev-stable", payload) is True
        assert await queue.enqueue("Ev-stable", payload) is False

    asyncio.run(exercise())
    assert redis.jobs == [("process_slack_event", "Ev-stable", "slack-event:Ev-stable")]
    assert "must-not-enter-job-arguments" not in repr(redis.jobs)
    assert "must-not-enter-job-arguments" in redis.values[RedisEventQueue.payload_key("Ev-stable")]


def test_ack_is_decoupled_from_processing() -> None:
    body = callback("Ev-fast-ack")
    started = time.monotonic()
    with TestClient(create_app(settings(), MemoryEventQueue(), AuditLogger())) as client:
        response = client.post("/slack/events", content=body, headers=signed_headers(body))
    assert response.status_code == 200
    assert time.monotonic() - started < 2.5


def test_permission_denied() -> None:
    engine = PermissionEngine(MemoryApprovalStore())

    async def exercise() -> None:
        with pytest.raises(PermissionDenied, match="ACTION_NOT_APPROVABLE"):
            await engine.request_approval(user="U_TEST", action="delete_namespace", arguments={"name": "x"})

    asyncio.run(exercise())
    AuditLogger().record(
        action="delete_namespace",
        user="U_TEST",
        decision="denied",
        error_code="ACTION_NOT_APPROVABLE",
    )


def test_approval_required() -> None:
    engine = PermissionEngine(MemoryApprovalStore(), ttl_seconds=60)

    async def exercise() -> None:
        approval = await engine.request_approval(
            user="U_TEST",
            action="scale_deployment",
            arguments={"deployment": "api", "replicas": 2},
            now=100,
        )
        assert approval.expires_at == 160
        assert len(approval.token) >= 16

    asyncio.run(exercise())
    AuditLogger().record(
        action="scale_deployment",
        user="U_TEST",
        decision="approval_required",
        arguments={"deployment": "api", "replicas": 2},
    )


def test_approval_bound_to_action() -> None:
    engine = PermissionEngine(MemoryApprovalStore(), ttl_seconds=60)

    async def exercise() -> None:
        approval = await engine.request_approval(
            user="U_TEST",
            action="scale_deployment",
            arguments={"deployment": "api", "replicas": 2},
            now=100,
        )
        with pytest.raises(PermissionDenied, match="APPROVAL_ACTION_MISMATCH"):
            await engine.consume_approval(
                token=approval.token,
                user="U_TEST",
                expected_action="restart_deployment",
                now=101,
            )

    asyncio.run(exercise())


def test_three_incident_intents() -> None:
    replies = MemoryReplyClient()
    processor = SlackEventProcessor(
        tools=FixtureToolClient(),
        replies=replies,
        permissions=PermissionEngine(MemoryApprovalStore()),
        mutation=MemoryMutationExecutor(),
        audit=AuditLogger(),
        namespace="insighthub-dev",
        approval_ttl_seconds=60,
    )

    async def exercise() -> None:
        for index, text in enumerate(("api healthy?", "ingest count today?", "which pods failing?"), 1):
            await processor.process(json.loads(callback(f"Ev-intent-{index}", text)))

    asyncio.run(exercise())
    rendered = "\n".join(str(message["text"]) for message in replies.messages)
    assert len(replies.messages) == 3
    assert "healthy" in rendered
    assert "4 document" in rendered
    assert "Không có pod lỗi" in rendered
