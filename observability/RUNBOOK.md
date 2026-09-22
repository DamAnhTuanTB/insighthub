# InsightHub alert runbook

Every alert in `observability/rules/day4-rules.yaml` links here. Each entry says
what the signal means, what to check first, and what would make the alert wrong.

The bands are statistical: mean + 3·stddev over a one hour window, offset by ten
minutes so an ongoing incident cannot inflate the band it is breaching. They are
not machine learning and they say nothing about causation.

## LLMLatencyAnomaly

**Signal** `insighthub:llm_latency_p95:5m` above its band and above 0.5s.

**Means** Generation is slower than the past hour. The histogram includes failed
provider calls, so a provider timing out looks like latency, not errors.

**Check first**
1. `insighthub:rag_latency_p95:5m` — if retrieval moved too, the cause is shared
   (database, CPU), not the model path.
2. Pod CPU panel — a throttled API pod slows everything it serves.
3. `insighthub_worker_queue_depth` — ingestion competing for the same database.

**False positive when** the baseline is shorter than one hour, or traffic is so
low that p95 is computed from a handful of requests.

**Local injection** `scripts/chaos/inject-llm-latency.sh`, which sets
`CHAOS_LLM_EXTRA_LATENCY_MS` on the API. Configuration refuses that flag unless
the deployment is in fixture mode.

## IngestionQueueBacklogAnomaly

**Signal** `insighthub:queue_depth:avg5m` above its band and above 5 jobs.

**Means** Jobs arrive faster than the worker drains them, or the worker is not
draining at all.

**Check first**
1. `insighthub_worker_up` — zero means no worker is serving.
2. `rate(insighthub_worker_jobs_total{outcome="retried"}[5m])` — sustained
   retries mean each job is consuming three attempts.
3. Worker pod restarts and `insighthub_worker_queue_poll_failures_total`.

**False positive when** a deliberate bulk upload is in progress. Depth alone is
not failure; depth that does not fall is.

**Local injection** `scripts/chaos/inject-queue-backlog.sh`, which scales the
worker to zero, uploads a batch, then restores it.

## APIErrorRateAnomaly

**Signal** `insighthub:http_error_ratio:5m` above its band and above 5%.

**Means** The API is returning 5xx. Upload validation failures are 4xx and are
deliberately excluded.

**Check first**
1. `up{namespace="insighthub-dev"}` and `pg_up` — a dependency being down is the
   usual cause.
2. API logs for the sanitized error code. Raw driver text is never logged.
3. Deployment annotations on the dashboard — a rollout immediately before the
   burst is the first suspect.

**False positive when** total request rate is near zero; the ratio is then
dominated by one or two requests.

**Local injection** `scripts/chaos/inject-error-burst.sh`, which scales the local
PostgreSQL dependency to zero for a bounded window.

## Escalation

This is a local lab. There is no on-call rotation, no paging, and no production
impact. Alertmanager delivers to a Slack channel for exercise purposes only.
