#!/usr/bin/env bash
# Incident 2: the worker stops draining while uploads keep arriving.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"
guard_local_context

UPLOAD_COUNT=${UPLOAD_COUNT:-40}
BASELINE_SECONDS=${BASELINE_SECONDS:-300}
FAILURE_SECONDS=${FAILURE_SECONDS:-600}
RECOVERY_SECONDS=${RECOVERY_SECONDS:-420}

BASELINE_START=$(date -u -v-"${BASELINE_SECONDS}"S +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "-${BASELINE_SECONDS} seconds" +%Y-%m-%dT%H:%M:%SZ)

printf 'Scaling the worker to zero...\n'
kube scale "deployment/$RELEASE-worker" --replicas=0 >/dev/null
kube wait --for=delete pod -l app.kubernetes.io/component=worker --timeout=120s >/dev/null 2>&1 || true
FAILURE_START=$(now)

printf 'Uploading %s documents into a queue nobody is draining...\n' "$UPLOAD_COUNT"
kube exec "deployment/$RELEASE-api" -- python -c "
import uuid, httpx
count = $UPLOAD_COUNT
body = (b'InsightHub backlog fixture document.\n' * 8)
with httpx.Client(base_url='http://127.0.0.1:8000', timeout=30) as client:
    accepted = 0
    for _ in range(count):
        name = 'backlog-' + uuid.uuid4().hex[:12] + '.txt'
        try:
            if client.post('/documents', files={'file': (name, body, 'text/plain')}).status_code == 202:
                accepted += 1
        except httpx.HTTPError:
            pass
    print('accepted', accepted, 'of', count)
"

sleep "$FAILURE_SECONDS"
FAILURE_END=$(now)

printf 'Restoring the worker...\n'
kube scale "deployment/$RELEASE-worker" --replicas=1 >/dev/null
kube rollout status "deployment/$RELEASE-worker" --timeout=5m >/dev/null

sleep "$RECOVERY_SECONDS"
RECOVERY_END=$(now)

write_window incident-2 "$BASELINE_START" "$FAILURE_START" "$FAILURE_END" "$RECOVERY_END" \
    "Worker scaled to zero with ${UPLOAD_COUNT} uploads queued; ARQ queue depth crosses its anomaly band."
