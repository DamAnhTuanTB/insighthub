"""Metrics published by the ARQ worker process only.

Kept out of app.core.metrics on purpose: that module is imported by the API,
and any counter declared there is exported on the API's /metrics endpoint as
a constant zero, which would shadow the worker's real series.
"""

from prometheus_client import Counter, Gauge, Histogram

worker_up = Gauge(
    "insighthub_worker_up",
    "1 while the ARQ worker process is serving jobs",
)
worker_queue_depth = Gauge(
    "insighthub_worker_queue_depth",
    "Jobs waiting in the ARQ queue, refreshed on a fixed interval",
)
worker_queue_poll_failures_total = Counter(
    "insighthub_worker_queue_poll_failures_total",
    "Queue depth refreshes that could not read Redis",
)
worker_jobs_total = Counter(
    "insighthub_worker_jobs_total",
    "Ingestion attempts by terminal outcome",
    ["outcome"],
)
worker_job_duration_seconds = Histogram(
    "insighthub_worker_job_duration_seconds",
    "Ingestion wall time per attempt, including retries",
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)
