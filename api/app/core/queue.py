"""ARQ queue lifecycle. Queue failures are sanitized before crossing the API."""

import asyncio
import logging

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings
from app.core.errors import QueueUnavailable

logger = logging.getLogger("insighthub.queue")
_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


def redis_settings() -> RedisSettings:
    """Build one canonical Redis configuration for both API and worker."""
    try:
        return RedisSettings.from_dsn(get_settings().redis_url)
    except (TypeError, ValueError):
        raise QueueUnavailable() from None


async def get_queue() -> ArqRedis:
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                try:
                    _pool = await create_pool(redis_settings())
                except Exception:
                    logger.warning("Redis queue connection failed")
                    raise QueueUnavailable() from None
    return _pool


async def enqueue_document(document_id: int, filename: str, content: bytes) -> str:
    """Enqueue exactly one durable job for a newly-created document row."""
    try:
        job = await (await get_queue()).enqueue_job(
            "ingest_document",
            document_id,
            filename,
            content,
            _job_id=f"ingest-{document_id}",
            _expires=3600,
        )
    except QueueUnavailable:
        raise
    except Exception:
        logger.warning("Redis enqueue failed: document_id=%s", document_id)
        raise QueueUnavailable() from None
    if job is None:
        logger.warning("Duplicate queue job rejected: document_id=%s", document_id)
        raise QueueUnavailable()
    return job.job_id


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
