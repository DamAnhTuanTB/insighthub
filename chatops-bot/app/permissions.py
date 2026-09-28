"""Three-tier authorization with short-lived approvals bound to exact requests."""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol


READ_ACTIONS = {"health", "ingestion_count", "failing_pods"}
WRITE_ACTIONS = {"scale_deployment", "restart_deployment", "rollback_deployment"}
DESTRUCTIVE_ACTIONS = {"delete_deployment", "delete_namespace", "delete_pod"}


@dataclass(frozen=True)
class Approval:
    token: str
    user: str
    action: str
    arguments: dict[str, Any]
    expires_at: float


class ApprovalStore(Protocol):
    async def put(self, approval: Approval, ttl_seconds: int) -> None: ...

    async def take(self, token: str) -> Approval | None: ...


class MemoryApprovalStore:
    def __init__(self) -> None:
        self._records: dict[str, Approval] = {}

    async def put(self, approval: Approval, ttl_seconds: int) -> None:
        self._records[approval.token] = approval

    async def take(self, token: str) -> Approval | None:
        return self._records.pop(token, None)


class RedisApprovalStore:
    def __init__(self, redis: Any, prefix: str = "chatops:approval:") -> None:
        self.redis = redis
        self.prefix = prefix

    async def put(self, approval: Approval, ttl_seconds: int) -> None:
        await self.redis.set(
            self.prefix + approval.token,
            json.dumps(asdict(approval), ensure_ascii=True, separators=(",", ":")),
            ex=ttl_seconds,
            nx=True,
        )

    async def take(self, token: str) -> Approval | None:
        raw = await self.redis.getdel(self.prefix + token)
        if raw is None:
            return None
        payload = json.loads(raw)
        return Approval(
            token=str(payload["token"]),
            user=str(payload["user"]),
            action=str(payload["action"]),
            arguments=dict(payload["arguments"]),
            expires_at=float(payload["expires_at"]),
        )


class PermissionDenied(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PermissionEngine:
    def __init__(self, store: ApprovalStore, ttl_seconds: int = 60) -> None:
        self.store = store
        self.ttl_seconds = ttl_seconds

    def tier(self, action: str) -> str:
        if action in READ_ACTIONS:
            return "read"
        if action in WRITE_ACTIONS:
            return "write"
        if action in DESTRUCTIVE_ACTIONS:
            return "destructive"
        return "unknown"

    def authorize_read(self, action: str) -> None:
        if self.tier(action) != "read":
            raise PermissionDenied("READ_ACTION_NOT_ALLOWED")

    async def request_approval(
        self,
        *,
        user: str,
        action: str,
        arguments: dict[str, Any],
        now: float | None = None,
    ) -> Approval:
        if self.tier(action) != "write":
            raise PermissionDenied("ACTION_NOT_APPROVABLE")
        created_at = time.time() if now is None else now
        approval = Approval(
            token=secrets.token_urlsafe(18),
            user=user,
            action=action,
            arguments=arguments,
            expires_at=created_at + self.ttl_seconds,
        )
        await self.store.put(approval, self.ttl_seconds)
        return approval

    async def consume_approval(
        self,
        *,
        token: str,
        user: str,
        expected_action: str | None = None,
        expected_arguments: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> Approval:
        approval = await self.store.take(token)
        if approval is None:
            raise PermissionDenied("APPROVAL_NOT_FOUND")
        current_time = time.time() if now is None else now
        if current_time > approval.expires_at:
            raise PermissionDenied("APPROVAL_EXPIRED")
        if not secrets.compare_digest(approval.user, user):
            raise PermissionDenied("APPROVAL_USER_MISMATCH")
        if expected_action is not None and approval.action != expected_action:
            raise PermissionDenied("APPROVAL_ACTION_MISMATCH")
        if expected_arguments is not None and approval.arguments != expected_arguments:
            raise PermissionDenied("APPROVAL_ARGUMENTS_MISMATCH")
        return approval
