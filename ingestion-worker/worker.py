"""ARQ worker entrypoint for bounded, idempotent document ingestion."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.core.db import close_pool, initialize_database
from app.core.errors import ServiceError
from app.core.queue import redis_settings
from app.services.ingestion import process_document
from arq import Retry

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
    try:
        chunk_count = await asyncio.to_thread(
            process_document, document_id, filename, content
        )
    except ServiceError as exc:
        if attempt < MAX_ATTEMPTS:
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
        _event(
            "ingestion_failed",
            document_id,
            status="failed",
            error_code=exc.code,
            attempt=attempt,
        )
        raise
    _event(
        "ingestion_completed",
        document_id,
        status="ready",
        chunk_count=chunk_count,
        attempt=attempt,
    )
    return chunk_count


async def startup(ctx: dict[str, Any]) -> None:
    await asyncio.to_thread(initialize_database)
    _event("worker_started", 0, status="ready")


async def shutdown(ctx: dict[str, Any]) -> None:
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
