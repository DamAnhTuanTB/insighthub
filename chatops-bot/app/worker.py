"""ARQ worker for Slack replies with bounded retries."""

from __future__ import annotations

import json
from typing import Any

from arq import Retry
from arq.connections import RedisSettings

from .audit import AuditLogger
from .config import Settings
from .mutation import KubectlMutationExecutor
from .permissions import PermissionEngine, RedisApprovalStore
from .processor import SlackEventProcessor
from .queueing import RedisEventQueue
from .slack import SlackReplyClient
from .tools import FixtureToolClient, StdioMcpClient, ToolError


async def startup(ctx: dict[str, Any]) -> None:
    settings = Settings.from_env()
    if not settings.worker_ready:
        raise RuntimeError("CHATOPS_WORKER_NOT_CONFIGURED")
    tools = (
        FixtureToolClient()
        if settings.tool_mode == "fixture"
        else StdioMcpClient(
            settings.repository_root,
            settings.mcp_timeout_seconds,
            settings.mcp_kubeconfig,
        )
    )
    ctx["processor"] = SlackEventProcessor(
        tools=tools,
        replies=SlackReplyClient(settings.bot_token),
        permissions=PermissionEngine(
            RedisApprovalStore(ctx["redis"]),
            ttl_seconds=settings.approval_ttl_seconds,
        ),
        mutation=KubectlMutationExecutor(
            settings.mutation_kubeconfig,
            settings.mutation_context,
            settings.namespace,
        ),
        audit=AuditLogger(),
        namespace=settings.namespace,
        approval_ttl_seconds=settings.approval_ttl_seconds,
    )


async def process_slack_event(ctx: dict[str, Any], event_id: str) -> None:
    processor: SlackEventProcessor = ctx["processor"]
    payload_key = RedisEventQueue.payload_key(event_id)
    raw_payload = await ctx["redis"].get(payload_key)
    if raw_payload is None:
        ctx["processor"].audit.record(
            event_id=event_id,
            action="process_slack_event",
            user="unknown",
            decision="denied",
            error_code="EVENT_PAYLOAD_MISSING",
        )
        return
    try:
        payload = json.loads(raw_payload)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        ctx["processor"].audit.record(
            event_id=event_id,
            action="process_slack_event",
            user="unknown",
            decision="denied",
            error_code="EVENT_PAYLOAD_INVALID",
        )
        await ctx["redis"].delete(payload_key)
        return
    try:
        await processor.process(payload)
    except ToolError:
        attempt = int(ctx.get("job_try", 1))
        if attempt < 3:
            raise Retry(defer=2 ** (attempt - 1))
        await ctx["redis"].delete(payload_key)
        raise
    await ctx["redis"].delete(payload_key)


class WorkerSettings:
    functions = [process_slack_event]
    on_startup = startup
    max_tries = 3
    job_timeout = 45
    keep_result = 0
    redis_settings = RedisSettings.from_dsn(Settings.from_env().redis_url)
