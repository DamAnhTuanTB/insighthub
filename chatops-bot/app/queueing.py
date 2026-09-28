"""Durable ARQ event queue plus a deterministic in-memory test adapter."""

from __future__ import annotations

import json
from typing import Any, Protocol

from arq.connections import ArqRedis, RedisSettings, create_pool


class EventQueue(Protocol):
    async def enqueue(self, event_id: str, payload: dict[str, Any]) -> bool: ...

    async def close(self) -> None: ...


class MemoryEventQueue:
    def __init__(self) -> None:
        self.event_ids: set[str] = set()
        self.jobs: list[dict[str, Any]] = []

    async def enqueue(self, event_id: str, payload: dict[str, Any]) -> bool:
        if event_id in self.event_ids:
            return False
        self.event_ids.add(event_id)
        self.jobs.append(payload)
        return True

    async def close(self) -> None:
        return None


class RedisEventQueue:
    def __init__(self, redis: ArqRedis, event_ttl_seconds: int = 86_400) -> None:
        self.redis = redis
        self.event_ttl_seconds = event_ttl_seconds

    @staticmethod
    def payload_key(event_id: str) -> str:
        return f"insighthub:chatops:event-payload:{event_id}"

    @staticmethod
    def seen_key(event_id: str) -> str:
        return f"insighthub:chatops:event-seen:{event_id}"

    @classmethod
    async def connect(cls, redis_url: str) -> "RedisEventQueue":
        return cls(await create_pool(RedisSettings.from_dsn(redis_url)))

    async def enqueue(self, event_id: str, payload: dict[str, Any]) -> bool:
        seen_key = self.seen_key(event_id)
        payload_key = self.payload_key(event_id)
        claimed = await self.redis.set(
            seen_key,
            "1",
            ex=self.event_ttl_seconds,
            nx=True,
        )
        if not claimed:
            return False
        try:
            await self.redis.set(
                payload_key,
                json.dumps(payload, separators=(",", ":")),
                ex=self.event_ttl_seconds,
            )
            job = await self.redis.enqueue_job(
                "process_slack_event",
                event_id,
                _job_id=f"slack-event:{event_id}",
            )
        except Exception:
            await self.redis.delete(seen_key, payload_key)
            raise
        return job is not None

    async def close(self) -> None:
        await self.redis.aclose()
