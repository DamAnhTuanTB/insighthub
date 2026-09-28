"""Slack event processing, read-only triage, and gated mutations."""

from __future__ import annotations

import json
import re
from typing import Any

from .audit import AuditLogger
from .intents import Intent, parse_intent
from .mutation import MutationError, MutationExecutor
from .permissions import PermissionDenied, PermissionEngine
from .slack import ReplyClient
from .tools import ToolClient, ToolError, content_text


def _prometheus_value(text: str) -> float | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    def find_value(value: Any) -> float | None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "value" and isinstance(item, list) and len(item) >= 2:
                    try:
                        return float(item[-1])
                    except (TypeError, ValueError):
                        pass
                found = find_value(item)
                if found is not None:
                    return found
        if isinstance(value, list):
            for item in value:
                found = find_value(item)
                if found is not None:
                    return found
        return None

    structured = find_value(payload)
    if structured is not None:
        return structured
    candidate = payload.get("result", text) if isinstance(payload, dict) else text
    candidate_text = candidate if isinstance(candidate, str) else text
    # prometheus-mcp renders instant vectors as `labels => value @[timestamp]`.
    rendered = re.search(r"=>\s*(-?\d+(?:\.\d+)?)\s*@\[", candidate_text)
    if rendered:
        return float(rendered.group(1))
    numbers = re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", candidate_text)
    return float(numbers[-1]) if numbers else None


def _failing_pod_summary(text: str) -> tuple[int, list[str]]:
    failing: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith(("name", "namespace")):
            continue
        if not any(status in stripped for status in ("Running", "Completed", "Succeeded")):
            name = stripped.split()[0]
            if re.fullmatch(r"[a-z0-9.-]+", name):
                failing.append(name)
    return len(failing), failing[:10]


class SlackEventProcessor:
    def __init__(
        self,
        *,
        tools: ToolClient,
        replies: ReplyClient,
        permissions: PermissionEngine,
        mutation: MutationExecutor,
        audit: AuditLogger,
        namespace: str,
        approval_ttl_seconds: int,
    ) -> None:
        self.tools = tools
        self.replies = replies
        self.permissions = permissions
        self.mutation = mutation
        self.audit = audit
        self.namespace = namespace
        self.approval_ttl_seconds = approval_ttl_seconds

    async def process(self, payload: dict[str, Any]) -> None:
        event_id = str(payload.get("event_id", "unknown"))
        event = payload.get("event")
        if not isinstance(event, dict):
            return
        user = event.get("user")
        channel = event.get("channel")
        text = event.get("text")
        if not all(isinstance(value, str) and value for value in (user, channel, text)):
            self.audit.record(
                event_id=event_id,
                action="process_slack_event",
                user=str(user or "unknown"),
                decision="denied",
                error_code="EVENT_FIELDS_INVALID",
            )
            return
        thread_ts = event.get("thread_ts") or event.get("ts")
        intent = parse_intent(text)
        response = await self._handle_intent(intent, user, event_id)
        await self.replies.send(channel, response, str(thread_ts) if thread_ts else None)

    async def _handle_intent(self, intent: Intent, user: str, event_id: str) -> str:
        if intent.name in {"health", "ingestion_count", "failing_pods"}:
            self.permissions.authorize_read(intent.name)
            return await self._read_intent(intent.name, user, event_id)
        if intent.name == "scale_deployment":
            return await self._request_scale(intent.arguments, user, event_id)
        if intent.name == "confirm":
            return await self._confirm(str(intent.arguments["token"]), user, event_id)
        if intent.name == "delete_deployment":
            self.audit.record(
                event_id=event_id,
                action="delete_deployment",
                user=user,
                decision="denied",
                error_code="DESTRUCTIVE_ACTION_DENIED",
            )
            return "Từ chối: hành động destructive không được phép qua ChatOps."
        self.audit.record(
            event_id=event_id,
            action="unknown_intent",
            user=user,
            decision="denied",
            error_code="INTENT_NOT_SUPPORTED",
        )
        return (
            "Mình hỗ trợ: `api healthy?`, `ingest count today?`, "
            "`which pods failing?`, và `scale api to 2`."
        )

    async def _read_intent(self, action: str, user: str, event_id: str) -> str:
        if action == "health":
            prometheus = await self._call_tool(
                backend="prometheus",
                tool="query",
                arguments={"query": 'min(up{job=~"insighthub.*"})'},
                action=action,
                user=user,
                event_id=event_id,
            )
            pods = await self._call_tool(
                backend="kubernetes",
                tool="pods_list_in_namespace",
                arguments={"namespace": self.namespace},
                action=action,
                user=user,
                event_id=event_id,
            )
            up = _prometheus_value(content_text(prometheus))
            failed, names = _failing_pod_summary(content_text(pods))
            healthy = up is not None and up >= 1 and failed == 0
            detail = "không có pod lỗi" if not names else "pod lỗi: " + ", ".join(names)
            return f"InsightHub {'healthy' if healthy else 'chưa healthy'}; {detail}."
        if action == "ingestion_count":
            result = await self._call_tool(
                backend="prometheus",
                tool="query",
                arguments={"query": 'sum(increase(insighthub_worker_jobs_total{outcome="completed"}[24h])) or vector(0)'},
                action=action,
                user=user,
                event_id=event_id,
            )
            count = _prometheus_value(content_text(result))
            rendered = int(round(count)) if count is not None else 0
            return f"Trong 24 giờ gần nhất, InsightHub ingest thành công {rendered} document."
        result = await self._call_tool(
            backend="kubernetes",
            tool="pods_list_in_namespace",
            arguments={"namespace": self.namespace},
            action=action,
            user=user,
            event_id=event_id,
        )
        failed, names = _failing_pod_summary(content_text(result))
        return "Không có pod lỗi." if failed == 0 else f"Có {failed} pod lỗi: {', '.join(names)}."

    async def _call_tool(
        self,
        *,
        backend: str,
        tool: str,
        arguments: dict[str, Any],
        action: str,
        user: str,
        event_id: str,
    ) -> dict[str, Any]:
        try:
            result = await self.tools.call(backend, tool, arguments)
        except ToolError as exc:
            self.audit.record(
                event_id=event_id,
                action=action,
                user=user,
                decision="denied",
                tool=f"{backend}.{tool}",
                arguments=arguments,
                error_code=exc.code,
            )
            raise
        self.audit.record(
            event_id=event_id,
            action=action,
            user=user,
            decision="allowed",
            tool=f"{backend}.{tool}",
            arguments=arguments,
            result="tool call completed",
        )
        return result

    async def _request_scale(self, arguments: dict[str, Any], user: str, event_id: str) -> str:
        deployment = arguments.get("deployment")
        replicas = arguments.get("replicas")
        if deployment not in {"api", "worker", "insighthub-api", "insighthub-worker"} or (
            type(replicas) is not int or not 1 <= replicas <= 5
        ):
            self.audit.record(
                event_id=event_id,
                action="scale_deployment",
                user=user,
                decision="denied",
                arguments=arguments,
                error_code="MUTATION_ARGUMENTS_DENIED",
            )
            return "Từ chối: chỉ scale api/worker trong khoảng 1–5 replicas."
        approval = await self.permissions.request_approval(
            user=user,
            action="scale_deployment",
            arguments=arguments,
        )
        self.audit.record(
            event_id=event_id,
            action="scale_deployment",
            user=user,
            decision="approval_required",
            arguments=arguments,
            result="short-lived approval issued",
        )
        return (
            f"Cần xác nhận scale {deployment} lên {replicas}. "
            f"Gửi `confirm {approval.token}` trong {self.approval_ttl_seconds} giây."
        )

    async def _confirm(self, token: str, user: str, event_id: str) -> str:
        try:
            approval = await self.permissions.consume_approval(token=token, user=user)
            result = await self.mutation.execute(approval.action, approval.arguments)
        except (PermissionDenied, MutationError) as exc:
            self.audit.record(
                event_id=event_id,
                action="confirm_mutation",
                user=user,
                decision="denied",
                error_code=exc.code,
            )
            return f"Không thể thực thi xác nhận ({exc.code})."
        self.audit.record(
            event_id=event_id,
            action=approval.action,
            user=user,
            decision="allowed",
            tool="kubernetes.mutation",
            arguments=approval.arguments,
            result="approved mutation completed",
        )
        return f"Đã thực thi: {result}."
