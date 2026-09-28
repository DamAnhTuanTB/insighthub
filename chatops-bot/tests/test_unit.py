from __future__ import annotations

import asyncio

import pytest

from app.intents import parse_intent
from app.permissions import MemoryApprovalStore, PermissionDenied, PermissionEngine
from app.processor import _prometheus_value
from app.security import SignatureError, slack_signature, verify_slack_signature


def test_signature_round_trip_and_replay_defense() -> None:
    body = b'{"type":"url_verification"}'
    signature = slack_signature("secret", "1000", body)
    verify_slack_signature(secret="secret", timestamp="1000", signature=signature, body=body, now=1001)
    with pytest.raises(SignatureError, match="SLACK_REQUEST_EXPIRED"):
        verify_slack_signature(secret="secret", timestamp="1000", signature=signature, body=body, now=1301)


def test_intent_parser_covers_required_questions() -> None:
    assert parse_intent("InsightHub có healthy không?").name == "health"
    assert parse_intent("Hôm nay ingest bao nhiêu doc?").name == "ingestion_count"
    assert parse_intent("Pod nào đang lỗi?").name == "failing_pods"
    assert parse_intent("scale api to 3").arguments == {"deployment": "api", "replicas": 3}


def test_approval_is_single_use_and_user_bound() -> None:
    engine = PermissionEngine(MemoryApprovalStore(), ttl_seconds=60)

    async def exercise() -> None:
        approval = await engine.request_approval(
            user="U1", action="scale_deployment", arguments={"deployment": "api", "replicas": 2}, now=10
        )
        with pytest.raises(PermissionDenied, match="APPROVAL_USER_MISMATCH"):
            await engine.consume_approval(token=approval.token, user="U2", now=11)
        with pytest.raises(PermissionDenied, match="APPROVAL_NOT_FOUND"):
            await engine.consume_approval(token=approval.token, user="U1", now=12)

    asyncio.run(exercise())


def test_prometheus_mcp_value_ignores_timestamp() -> None:
    rendered = '{"result":"{} => 4 @[1790584422.866]","warnings":null}'
    assert _prometheus_value(rendered) == 4
