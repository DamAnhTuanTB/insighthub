# Day 4 observability implementation review

## Scope and provenance

- Platform: local `kind` cluster `kind-insighthub-day2`, Kubernetes server
  `v1.37.0`, kind `v0.33.0`, all inside Docker Desktop on the developer laptop.
- Monitoring: `kube-prometheus-stack` chart `91.4.1` (operator `v0.94.0`) in
  namespace `monitoring`, installed by `scripts/day4/monitoring-install.sh`.
- Application: the Day 3 Helm release in namespace `insighthub-dev`, with the
  Day 4 observability overlay `infra/helm/insighthub/values-observability.yaml`.
- AWS verified: **false**. This work claims no EKS, Amazon Managed Prometheus,
  Amazon Managed Grafana, CloudWatch, RDS, ElastiCache, IRSA, or AWS billing.
  Grafana, Prometheus and Alertmanager are pods on the local cluster, not
  Grafana Cloud.
- Model providers remain fixture. No paid provider was called for Day 4.

## Five-component coverage

| Component | Mechanism | Target |
|---|---|---|
| api | `/metrics` on port 8000 | ServiceMonitor `insighthub-api` |
| ingestion-worker | `/metrics` on port 9101 | ServiceMonitor `insighthub-worker` |
| postgres | `postgres_exporter` | ServiceMonitor `insighthub-postgres-exporter` |
| redis | `redis_exporter` | ServiceMonitor `insighthub-redis-exporter` |
| web | blackbox HTTP probe | Probe `insighthub-web` |

Next.js exposes no metrics endpoint, so web availability is probed externally
rather than instrumented. `kube-state-metrics` and cAdvisor supply pod resource
and rollout-annotation series.

## Implemented

- Worker instrumentation: queue depth, job outcome counters, job duration
  histogram and a liveness gauge, published from a dedicated metrics module so
  the API cannot shadow them with constant zeros.
- Exporters for PostgreSQL and Redis with credentials read from mounted Secret
  files, plus a blackbox exporter for the web probe. NetworkPolicies open the
  metrics ports to the `monitoring` namespace only.
- One rule file as the source of truth, wrapped into a PrometheusRule CRD by
  `scripts/day4/render-prometheusrule.py` so the tested file and the running
  rules cannot diverge.
- Grafana dashboard with 11 query panels covering RED, USE, queue saturation,
  token usage, estimated cost and rollout annotations.
- Alertmanager routing to Slack `#alerts`, with the webhook stored only in the
  namespace Secret `monitoring/alertmanager-slack`.
- Bounded, reversible fault injection for three separate incidents, each script
  recording its own baseline/failure/recovery window.

## Verification results

- `promtool check rules`: 21 rules, SUCCESS.
- `promtool test rules`: SUCCESS. Each case asserts the band stays quiet during
  baseline and fires after injection.
- Conftest on the rendered chart with observability enabled: 360 passed, 0 failed.
- Checkov on the same render: 705 passed, 0 failed, 8 documented skips.
- Worker unit tests 4 passed; API unit tests 50 passed; Day 1 milestone suite
  6 passed after the worker change.
- All scrape targets UP, covering the five components.
- Slack delivery confirmed twice: a synthetic alert during setup, then all three
  real incident alerts. `evidence/day4-alerting.json` records 8 notifications
  sent and 0 failed, taken from Alertmanager's own counters.
- `scripts/verify.py day4` returns PASS with `runtime_verified: true`,
  `incidents_checked: 3` and `samples_checked: 36` against
  `source_sha256 75814859497e78805dff1e187a802e49ab57e2c48076e7d7ef601d825c42716c`.
  Its scope stays `partial-runtime-contract`; `milestone_complete` is false and
  specification review is still required.

## Incident results

Baseline before the first injection: 124 minutes of continuous telemetry. The
queue band restarted at 14:49Z when its recording rule was redefined to read
Redis, and its incident waited a further 71 minutes rather than reusing a
baseline that no longer applied.

| # | Alert | Fired | Failure window (UTC) | Cited samples | Confidence |
|---|---|---|---|---|---|
| 1 | `LLMLatencyAnomaly` | 22 firing samples | 14:49:42–14:59:42 | 12 | 0.95 |
| 2 | `IngestionQueueBacklogAnomaly` | 22 firing samples | 16:00:02–16:10:02 | 12 | 0.96 |
| 3 | `APIErrorRateAnomaly` | 19 firing samples | 15:05:54–15:15:54 | 12 | 0.93 |

All three alerts reached Slack `#alerts`. All 36 cited samples were re-queried
against live Prometheus and matched within 1e-6, using the same comparison the
verifier performs.

| # | Signal during the incident | What ruled out the alternatives |
|---|---|---|
| 1 | LLM p95 0.2375 → 9.75s | api CPU ~0.004 of a 1 core limit; queue depth 0; error ratio 0; RAG p95 moved identically, placing the delay in generation |
| 2 | Queue depth 0 → 41, Redis-measured | worker gauge and `insighthub_worker_up` had no samples at all in the window; the only worker pod was created after it closed |
| 3 | 5xx ratio 0 → 0.1058 | `pg_up` and `up` held at 1; latency unchanged at 0.2375s, so requests failed fast rather than timing out |

Incident 2 is also the evidence for a design decision: an earlier version of the
queue rule read the worker's own gauge, and that series disappears exactly when
the worker is the fault. The alert could not have fired. Measuring the ARQ sorted
set through `redis_exporter` keeps the signal alive through the failure it is
meant to detect.

## MCP access boundary

RCA used the Day 2 Prometheus and Kubernetes MCP backends. The Kubernetes
ServiceAccount was bound to a second namespace-scoped RoleBinding so it could
read the application namespace; `evidence/day4-rbac.json` records the resulting
boundary. Reads of pods, logs and services in `insighthub-dev` are allowed;
Secrets, mutations, and the `monitoring` namespace are all denied.

## Defects found and fixed during implementation

1. **Worker metrics shadowed by the API.** Declaring them in `app.core.metrics`
   meant the API, which imports that module, exported every worker counter as a
   constant zero and produced duplicate series. Moved to `app.core.worker_metrics`.
2. **Error-ratio recording rule returned empty.** With no 5xx traffic there is no
   matching series, so the division produced nothing and the baseline never
   formed — the alert could not have fired during a real error burst. Fixed with
   `or vector(0)` on the aggregations.
3. **Anomaly band inflated by its own incident.** A one hour trailing window
   absorbed the failure, widened the band, and cleared the alert while the
   failure was still running. Fixed by offsetting the baseline window by ten
   minutes.
4. **NaN poisoned the latency baseline.** A quantile over a window with no
   requests is NaN, and NaN propagates through `avg_over_time`, so the latency
   band stayed NaN indefinitely. The p95 rules now emit no sample when there is
   no traffic, which `avg_over_time` skips.
5. **Queue depth published by the worker itself.** The first run of all three
   incidents produced no alerts at all. Scaling the worker to zero removed the
   very series that was supposed to report the backlog, so the signal vanished
   at the moment it mattered. Queue depth now comes from `redis_exporter`
   reading the ARQ sorted set, and the rule test models the worker's samples
   disappearing so the regression cannot return unnoticed.
6. **Database removal produced silence, not errors.** Scaling PostgreSQL to zero
   failed the readiness probe, took the API out of the Service, and left no
   requests to fail - an outage with no error signal. The error scenario now
   injects failures inside the chat handler so the API keeps serving and the
   5xx ratio is measurable.
7. **RCA timestamps truncated downwards.** Rounding a sample timestamp down to
   whole seconds could land just before the cited sample, so a re-query returned
   the previous value and a real citation looked fabricated. Timestamps now round
   up.
8. **Exporter credentials passed as environment variables.** Flagged by Checkov
   CKV_K8S_35 and fixed by mounting Secret files; `redis_exporter` needs a JSON
   address-to-password map, rendered by an init container.

## Boundary statements

- The anomaly bands are statistical (mean + 3·stddev), not machine learning, and
  describe deviation from the recent past rather than correctness.
- The cost panel applies declared unit prices to observed token rates. Fixture
  mode reports no provider LLM tokens at all, so that series is legitimately
  empty; no figure was substituted.
- Every RCA citation was collected from Prometheus by
  `scripts/day4/collect-samples.py`. `scripts/day4/build-rca.py` refuses an
  analysis file that names a metric which was not collected.
- Baseline duration is recorded as observed. It was not shortened to produce an
  earlier alert.
