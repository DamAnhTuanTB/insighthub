"""Structured, bounded audit events for every ChatOps decision and tool call."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


logger = logging.getLogger("chatops.audit")
_SENSITIVE_KEYS = ("authorization", "password", "secret", "signature", "token")


def _sanitize(value: Any, key: str = "") -> Any:
    if any(part in key.lower() for part in _SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value[:20]]
    if isinstance(value, str):
        return value[:256]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:256]


class AuditLogger:
    """Emit JSON lines and, during verification, a correlated observation file."""

    def __init__(
        self,
        path: Path | None = None,
        observation_path: Path | None = None,
        test_run_id: str | None = None,
    ) -> None:
        configured_path = os.environ.get("CHATOPS_AUDIT_LOG")
        configured_observation = os.environ.get("INSIGHTHUB_VERIFY_OBSERVATIONS")
        self.path = path or (Path(configured_path) if configured_path else None)
        self.observation_path = observation_path or (
            Path(configured_observation) if configured_observation else None
        )
        self.test_run_id = test_run_id or os.environ.get("INSIGHTHUB_VERIFY_RUN_ID")
        self._lock = Lock()

    def record(
        self,
        *,
        action: str,
        user: str,
        decision: str,
        tool: str | None = None,
        arguments: dict[str, Any] | None = None,
        result: str | None = None,
        error_code: str | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        if decision not in {"allowed", "denied", "approval_required"}:
            raise ValueError("unsupported audit decision")
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": event_id or uuid4().hex,
            "user": user or "unknown",
            "action": action,
            "decision": decision,
        }
        if self.test_run_id:
            record["test_run_id"] = self.test_run_id
        if tool:
            record["tool"] = tool
        if arguments is not None:
            record["arguments"] = _sanitize(arguments)
        if result:
            record["result"] = _sanitize(result)
        if error_code:
            record["error_code"] = error_code

        encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        logger.info(encoded)
        with self._lock:
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(encoded + "\n")
            if self.observation_path and self.test_run_id:
                self._append_observation(record)
        return record

    def _append_observation(self, record: dict[str, Any]) -> None:
        assert self.observation_path is not None
        existing: dict[str, Any] = {"run_id": self.test_run_id, "events": []}
        if self.observation_path.exists():
            try:
                loaded = json.loads(self.observation_path.read_text(encoding="utf-8"))
                if loaded.get("run_id") == self.test_run_id and isinstance(loaded.get("events"), list):
                    existing = loaded
            except (OSError, ValueError, AttributeError):
                pass
        existing["events"].append(record)
        self.observation_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.observation_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.observation_path)


def log_tool_call(
    user: str,
    tool: str,
    args: dict[str, Any],
    result_summary: str,
    approved: bool = True,
) -> None:
    """Backward-compatible helper for callers that do not retain an AuditLogger."""

    AuditLogger().record(
        action="tool_call",
        user=user,
        decision="allowed" if approved else "denied",
        tool=tool,
        arguments=args,
        result=result_summary,
    )
