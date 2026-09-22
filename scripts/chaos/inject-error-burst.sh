#!/usr/bin/env bash
# Incident 3: the API starts failing a share of chat requests.
#
# Removing the database instead would fail the readiness probe, take the pod out
# of the Service, and produce no requests at all rather than failed ones - an
# outage with no error signal. Injecting the failure inside the handler keeps the
# API serving, so the 5xx ratio is actually observable.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"
guard_local_context

ERROR_RATIO=${ERROR_RATIO:-0.6}
BASELINE_SECONDS=${BASELINE_SECONDS:-300}
FAILURE_SECONDS=${FAILURE_SECONDS:-600}
RECOVERY_SECONDS=${RECOVERY_SECONDS:-360}

MODE=$(kube get configmap settings -o jsonpath='{.data.RAG_MODE}')
if [ "$MODE" != "fixture" ]; then
    printf 'Refusing: deployment is in %s mode, not fixture.\n' "$MODE" >&2
    exit 2
fi

BASELINE_START=$(date -u -v-"${BASELINE_SECONDS}"S +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "-${BASELINE_SECONDS} seconds" +%Y-%m-%dT%H:%M:%SZ)

printf 'Injecting a %s failure ratio into chat...\n' "$ERROR_RATIO"
kube set env "deployment/$RELEASE-api" CHAOS_ENABLED=true "CHAOS_CHAT_ERROR_RATIO=$ERROR_RATIO" >/dev/null
kube rollout status "deployment/$RELEASE-api" --timeout=5m >/dev/null
FAILURE_START=$(now)

sleep "$FAILURE_SECONDS"

FAILURE_END=$(now)
printf 'Removing the injected failures...\n'
kube set env "deployment/$RELEASE-api" CHAOS_ENABLED- CHAOS_CHAT_ERROR_RATIO- >/dev/null
kube rollout status "deployment/$RELEASE-api" --timeout=5m >/dev/null

sleep "$RECOVERY_SECONDS"
RECOVERY_END=$(now)

write_window incident-3 "$BASELINE_START" "$FAILURE_START" "$FAILURE_END" "$RECOVERY_END" \
    "Chat handler returned 5xx for ${ERROR_RATIO} of requests; API 5xx ratio crosses its anomaly band while pg_up and up stay 1."
