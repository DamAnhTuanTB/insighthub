#!/usr/bin/env bash
# One-screen Day 4 readiness check: targets, rules, alerts, baseline age.
set -eu

PROMETHEUS_URL=${PROMETHEUS_URL:-http://127.0.0.1:9090}
NAMESPACE=${NAMESPACE:-insighthub-dev}
MONITORING_NAMESPACE=${MONITORING_NAMESPACE:-monitoring}

printf '== ServiceMonitors / Probe ==\n'
kubectl get servicemonitor,probe -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{print "  " $1}'

printf '\n== Scrape targets ==\n'
curl -s "$PROMETHEUS_URL/api/v1/targets?state=active" | python3 -c "
import json, sys
groups = {}
for t in json.load(sys.stdin)['data']['activeTargets']:
    groups.setdefault(t['labels'].get('job', '?'), []).append(t['health'])
for job in sorted(groups):
    health = groups[job]
    flag = 'ok ' if all(h == 'up' for h in health) else 'DOWN'
    print(f\"  {flag} {job:38s} {health.count('up')}/{len(health)}\")
"

printf '\n== Anomaly bands (need ~70 minutes of baseline) ==\n'
for band in insighthub:llm_latency_p95:anomaly_upper insighthub:queue_depth:anomaly_upper insighthub:http_error_ratio:anomaly_upper; do
    printf '  %-46s ' "$band"
    curl -s --get "$PROMETHEUS_URL/api/v1/query" --data-urlencode "query=$band" | python3 -c "
import json, sys
r = json.load(sys.stdin).get('data', {}).get('result', [])
print(r[0]['value'][1] if r else 'not ready')
"
done

printf '\n== Alerts ==\n'
curl -s "$PROMETHEUS_URL/api/v1/rules?type=alert" | python3 -c "
import json, sys
for g in json.load(sys.stdin)['data']['groups']:
    for r in g['rules']:
        print(f\"  {r['name']:34s} {r['state']}\")
"
