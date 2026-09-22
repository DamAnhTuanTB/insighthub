# Day 4 - AIOps and MLOps prompt log

## Request

Build Day 4 entirely on the local machine. No AWS account exists, so Kubernetes
is a local `kind` cluster and the monitoring stack runs inside it. Reuse the
Day 1 worker, the Day 2 MCP backends and the Day 3 Helm/Terraform deployment
rather than rebuilding them.

## Accepted decisions

1. Run `kube-prometheus-stack` in a `monitoring` namespace on the same kind
   cluster. ServiceMonitor is the only way to satisfy MH1/MH2 honestly, and it
   requires the Prometheus Operator.
2. Cover the five components by the mechanism each one actually supports: API
   and worker expose `/metrics`, PostgreSQL and Redis get exporters, and web is
   probed by blackbox because Next.js serves no metrics endpoint. Inventing a
   metrics route in the web app would have been more code for a weaker signal.
3. Publish worker metrics from a dedicated `app.core.worker_metrics` module.
   The first attempt put them in `app.core.metrics`, which the API also imports,
   so the API exported every worker counter as a constant zero and doubled the
   series. Found by reading the live scrape, not by a test.
4. Keep one rule file as the source of truth and generate the PrometheusRule CRD
   from it. A hand-maintained copy in the cluster would drift from the file that
   promtool validates and that the evidence envelope submits.
5. Offset the one hour baseline window by ten minutes. Without the offset a
   sustained incident inflates its own band, the alert clears while the failure
   is still running, and the operator sees a resolved alert during an outage.
6. Wrap possibly-empty aggregations in `or vector(0)`. A window with no 5xx has
   no series at all, so the error ratio returned empty and its baseline never
   formed — the alert could not have fired in a real error burst.
7. Collect every RCA sample with a script that reads Prometheus directly, and
   forbid the analysis file from introducing its own numbers. The verifier
   re-queries each citation at `1e-6`; a model-authored figure would be both
   fabrication and an automatic FAIL.
8. Gate fault injection behind configuration: `CHAOS_ENABLED` is rejected unless
   the deployment is in fixture mode, and each chaos script refuses any
   kube-context that is not local.
9. Read exporter credentials from mounted files rather than environment
   variables, after Checkov flagged CKV_K8S_35. `redis_exporter` expects a JSON
   address-to-password map, so an init container renders one from the Secret
   using the Redis image already pinned in the chart.

## Rejected decisions

1. Do not run the observability stack in Docker Compose. It would be lighter but
   produces no ServiceMonitor, so MH1 would be unmet while the write-up implied
   otherwise.
2. Do not shorten the baseline below one hour to reach an alert sooner. The
   specification calls that out explicitly; an under-baselined band reports
   noise as anomaly.
3. Do not derive all three incidents from one injection. Three separate
   scenarios are required, and a single fault would not exercise the different
   detection paths (gauge, ratio, histogram).
4. Do not let the RCA agent read metrics and then write the numbers into the
   report from memory. Summarized values drift; cited values must be re-queryable.
5. Do not present the cost panel as a provider invoice. It applies declared unit
   prices to observed token rates, and fixture mode reports no provider tokens
   at all.
6. Do not claim Grafana Cloud, Amazon Managed Prometheus or EKS anywhere. The
   evidence review states the local boundary in the same terms Day 3 used.
7. Do not commit the Slack webhook or the Grafana admin password. Both live only
   in namespace Secrets, created at deploy time.

## Review notes

- promtool `check rules` and `test rules` both pass; the unit tests assert that
  each band stays quiet during baseline and fires after the injection, which is
  what makes them tests rather than syntax checks.
- Conftest (360 assertions) and Checkov (705 checks) pass on the rendered chart
  with observability enabled.
- Day 1 worker unit tests, API unit tests and the Day 1 milestone suite were
  re-run after the worker change; retry, idempotency and log sanitization are
  unaffected.
- Slack delivery was verified with a synthetic alert posted through the
  Alertmanager API and observed in `#alerts`.
