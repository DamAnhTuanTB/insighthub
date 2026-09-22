"""ARQ worker entrypoint for bounded, idempotent document ingestion."""

import asyncio
import contextlib
import json
import time
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.db import close_pool, initialize_database
from app.core.errors import ServiceError
from app.core.queue import redis_settings
from app.core.worker_metrics import (
    worker_job_duration_seconds,
    worker_jobs_total,
    worker_queue_depth,
    worker_queue_poll_failures_total,
    worker_up,
)
from app.services.ingestion import process_document
from arq import Retry
from arq.constants import default_queue_name
from prometheus_client import start_http_server

MAX_ATTEMPTS = 3

# ARQ's default INFO line renders job arguments, including uploaded bytes. The
# application emits its own sanitized JSON events instead.
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "CRITICAL"},
    "loggers": {
        "arq.worker": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "insighthub.ingestion": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}


def _event(name: str, document_id: int, **fields: object) -> None:
    """Emit one machine-readable line without filenames, content, or secrets."""
    payload = {
        "event": name,
        "document_id": document_id,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **fields,
    }
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True), flush=True)


async def ingest_document(
    ctx: dict[str, Any], document_id: int, filename: str, content: bytes
) -> int:
    """Run blocking ingestion off-loop and retry at most three total attempts."""
    attempt = int(ctx.get("job_try", 1))
    started = time.perf_counter()
    try:
        chunk_count = await asyncio.to_thread(
            process_document, document_id, filename, content
        )
    except ServiceError as exc:
        worker_job_duration_seconds.observe(time.perf_counter() - started)
        if attempt < MAX_ATTEMPTS:
            worker_jobs_total.labels("retried").inc()
            delay_seconds = 2 ** (attempt - 1)
            _event(
                "ingestion_retry",
                document_id,
                status="failed",
                error_code=exc.code,
                attempt=attempt,
                retry_in_seconds=delay_seconds,
            )
            raise Retry(defer=delay_seconds) from None
        worker_jobs_total.labels("failed").inc()
        _event(
            "ingestion_failed",
            document_id,
            status="failed",
            error_code=exc.code,
            attempt=attempt,
        )
        raise
    worker_job_duration_seconds.observe(time.perf_counter() - started)
    worker_jobs_total.labels("completed").inc()
    _event(
        "ingestion_completed",
        document_id,
        status="ready",
        chunk_count=chunk_count,
        attempt=attempt,
    )
    return chunk_count


async def _refresh_queue_depth(ctx: dict[str, Any], interval: float) -> None:
    """Publish queue saturation without touching job payloads."""
    redis = ctx["redis"]
    while True:
        try:
            worker_queue_depth.set(await redis.zcard(default_queue_name))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Redis details stay out of the logs; the counter is the signal.
            worker_queue_poll_failures_total.inc()
        await asyncio.sleep(interval)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    await asyncio.to_thread(initialize_database)
    # Scraped by Prometheus; the endpoint exposes counters only, never payloads.
    start_http_server(settings.worker_metrics_port)
    worker_up.set(1)
    ctx["queue_depth_task"] = asyncio.create_task(
        _refresh_queue_depth(ctx, settings.worker_queue_poll_seconds)
    )
    _event("worker_started", 0, status="ready")


async def shutdown(ctx: dict[str, Any]) -> None:
    task = ctx.pop("queue_depth_task", None)
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    worker_up.set(0)
    await asyncio.to_thread(close_pool)
    _event("worker_stopped", 0, status="stopped")


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    max_tries = MAX_ATTEMPTS
    job_timeout = 300
    # Results include serialized job arguments; delete them immediately after success.
    keep_result = 0
    health_check_interval = 15
    health_check_key = "insighthub:worker:health"
    job_completion_wait = 30
