"""Small deterministic intent parser; infrastructure output never controls actions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Intent:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


def parse_intent(text: str) -> Intent:
    normalized = " ".join(text.lower().replace("?", " ").split())
    normalized = re.sub(r"<@[a-z0-9]+>", "", normalized, flags=re.IGNORECASE).strip()
    confirmation = re.search(r"\b(?:confirm|xác nhận)\s+([A-Za-z0-9_-]{16,})\b", normalized)
    if confirmation:
        return Intent("confirm", {"token": confirmation.group(1)})
    scale = re.search(
        r"\b(?:scale|tăng|giảm)\s+(?:deployment\s+)?([a-z0-9-]+)(?:\s+(?:to|lên|xuống))?\s+(\d+)\b",
        normalized,
    )
    if scale:
        return Intent("scale_deployment", {"deployment": scale.group(1), "replicas": int(scale.group(2))})
    if any(term in normalized for term in ("delete", "xóa", "xoá")):
        return Intent("delete_deployment")
    if "pod" in normalized and any(term in normalized for term in ("lỗi", "loi", "fail", "error", "crash")):
        return Intent("failing_pods")
    if "ingest" in normalized and any(
        term in normalized for term in ("bao nhiêu", "bao nhieu", "how many", "count", "hôm nay", "today")
    ):
        return Intent("ingestion_count")
    if any(term in normalized for term in ("healthy", "health", "status", "khỏe", "khoe", "ổn không", "on khong")):
        return Intent("health")
    return Intent("unknown")
