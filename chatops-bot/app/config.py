"""Environment configuration for the local ChatOps ingress and worker."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    signing_secret: str
    bot_token: str
    bot_user_id: str
    redis_url: str
    queue_mode: str
    tool_mode: str
    namespace: str
    repository_root: Path
    signature_tolerance_seconds: int = 300
    approval_ttl_seconds: int = 60
    mcp_timeout_seconds: int = 15
    mcp_kubeconfig: Path | None = None
    mutation_kubeconfig: Path | None = None
    mutation_context: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        queue_mode = os.environ.get("CHATOPS_QUEUE_MODE", "redis").strip().lower()
        tool_mode = os.environ.get("CHATOPS_TOOL_MODE", "mcp").strip().lower()
        if queue_mode not in {"memory", "redis"}:
            raise ValueError("CHATOPS_QUEUE_MODE must be memory or redis")
        if tool_mode not in {"fixture", "mcp"}:
            raise ValueError("CHATOPS_TOOL_MODE must be fixture or mcp")
        configured_root = os.environ.get("INSIGHTHUB_REPO_ROOT")
        root = Path(configured_root).resolve() if configured_root else Path(__file__).resolve().parents[2]
        kubeconfig = os.environ.get("CHATOPS_MUTATION_KUBECONFIG")
        mcp_kubeconfig = os.environ.get("CHATOPS_MCP_KUBECONFIG")
        return cls(
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
            bot_token=os.environ.get("SLACK_BOT_TOKEN", ""),
            bot_user_id=os.environ.get("SLACK_BOT_USER_ID", ""),
            redis_url=os.environ.get("CHATOPS_REDIS_URL", "redis://127.0.0.1:6379/1"),
            queue_mode=queue_mode,
            tool_mode=tool_mode,
            namespace=os.environ.get("CHATOPS_NAMESPACE", "insighthub-dev"),
            repository_root=root,
            signature_tolerance_seconds=_integer("SLACK_SIGNATURE_TOLERANCE_SECONDS", 300, 1, 900),
            approval_ttl_seconds=_integer("CHATOPS_APPROVAL_TTL_SECONDS", 60, 5, 600),
            mcp_timeout_seconds=_integer("CHATOPS_MCP_TIMEOUT_SECONDS", 15, 1, 60),
            mcp_kubeconfig=(
                Path(mcp_kubeconfig).resolve()
                if mcp_kubeconfig
                else root / "tmp" / "day5" / "mcp-readonly.yaml"
            ),
            mutation_kubeconfig=Path(kubeconfig).resolve() if kubeconfig else None,
            mutation_context=os.environ.get("CHATOPS_MUTATION_CONTEXT", ""),
        )

    @property
    def ingress_ready(self) -> bool:
        return bool(self.signing_secret) and self.queue_mode in {"memory", "redis"}

    @property
    def worker_ready(self) -> bool:
        return bool(self.bot_token) and self.tool_mode in {"fixture", "mcp"}
