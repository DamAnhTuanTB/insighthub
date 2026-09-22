#!/usr/bin/env bash
# Run the three Day 4 incidents back to back and collect their evidence.
#
# The baseline gate is not negotiable: the bands use a one hour window offset by
# ten minutes, so nothing below 70 minutes of telemetry produces a meaningful
# alert. The script waits rather than lowering the threshold.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PROMETHEUS_URL=${PROMETHEUS_URL:-http://127.0.0.1:9090}
TIMELINE=${TIMELINE:-$REPO_ROOT/tmp/day4/timeline.json}
REQUIRED_MINUTES=${REQUIRED_MINUTES:-70}

cd "$REPO_ROOT"

wait_for_baseline() {
    # wait_for_baseline [timeline key]; a redefined recording rule starts a fresh
    # series and therefore a fresh baseline, tracked under its own key.
    python3 - "$TIMELINE" "$REQUIRED_MINUTES" "${1:-baseline_started_at}" <<'PY'
import json, sys, time
from datetime import UTC, datetime

timeline, required, key = sys.argv[1], float(sys.argv[2]), sys.argv[3]
start = datetime.strptime(
    json.load(open(timeline))[key], "%Y-%m-%dT%H:%M:%SZ"
).replace(tzinfo=UTC)
while True:
    elapsed = (datetime.now(UTC) - start).total_seconds() / 60
    if elapsed >= required:
        print(f"baseline ready: {elapsed:.0f} minutes")
        break
    print(f"baseline {elapsed:.0f}/{required:.0f} minutes; waiting", flush=True)
    time.sleep(60)
PY
}

run_one() {
    # run_one <number> <script>
    local number=$1 script=$2
    printf '\n=== incident %s: %s ===\n' "$number" "$script"
    NAMESPACE="${NAMESPACE:-insighthub-dev}" KUBE_CONTEXT="${KUBE_CONTEXT:-}" \
        FAILURE_SECONDS="${FAILURE_SECONDS:-600}" RECOVERY_SECONDS="${RECOVERY_SECONDS:-360}" \
        "$SCRIPT_DIR/../chaos/$script"
    python3 "$SCRIPT_DIR/collect-samples.py" \
        --window "tmp/day4/incident-$number.json" \
        --prometheus-url "$PROMETHEUS_URL" \
        --output "tmp/day4/incident-$number-samples.json"
    # Record whether the alert actually fired during the window.
    python3 - "$number" <<'PY'
import json, sys, urllib.parse, urllib.request
from datetime import UTC, datetime

number = sys.argv[1]
alert = {"1": "LLMLatencyAnomaly", "2": "IngestionQueueBacklogAnomaly", "3": "APIErrorRateAnomaly"}[number]
window = json.load(open(f"tmp/day4/incident-{number}.json"))


def stamp(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()


params = urllib.parse.urlencode({
    "query": f'ALERTS{{alertname="{alert}",alertstate="firing"}}',
    "start": stamp(window["failure_start"]),
    "end": stamp(window["recovery_end"]),
    "step": 30,
})
with urllib.request.urlopen(f"http://127.0.0.1:9090/api/v1/query_range?{params}", timeout=20) as r:
    result = json.loads(r.read().decode())["data"]["result"]
points = sum(len(s.get("values", [])) for s in result)
window["alert_fired"] = points > 0
window["alert_name"] = alert
window["alert_firing_samples"] = points
json.dump(window, open(f"tmp/day4/incident-{number}.json", "w"), indent=2)
print(f"{alert}: {'FIRED' if points else 'did not fire'} ({points} firing samples)")
PY
}

# Latency and error bands still hold their original baseline.
wait_for_baseline baseline_started_at
run_one 1 inject-llm-latency.sh
run_one 3 inject-error-burst.sh
# The queue rule was redefined to read Redis, so its band restarts from there.
wait_for_baseline queue_metric_baseline_started_at
run_one 2 inject-queue-backlog.sh

printf '\nAll three incidents complete.\n'
