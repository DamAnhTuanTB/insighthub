#!/usr/bin/env bash
# Incident 1: generation slows down. Fixture mode only, bounded, reversible.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"
guard_local_context

EXTRA_LATENCY_MS=${EXTRA_LATENCY_MS:-6000}
BASELINE_SECONDS=${BASELINE_SECONDS:-300}
FAILURE_SECONDS=${FAILURE_SECONDS:-600}
RECOVERY_SECONDS=${RECOVERY_SECONDS:-420}

MODE=$(kube get configmap settings -o jsonpath='{.data.RAG_MODE}')
if [ "$MODE" != "fixture" ]; then
    printf 'Refusing: deployment is in %s mode, not fixture.\n' "$MODE" >&2
    exit 2
fi

BASELINE_START=$(date -u -v-"${BASELINE_SECONDS}"S +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "-${BASELINE_SECONDS} seconds" +%Y-%m-%dT%H:%M:%SZ)

printf 'Injecting %s ms of fixture generation latency...\n' "$EXTRA_LATENCY_MS"
kube set env "deployment/$RELEASE-api" CHAOS_ENABLED=true "CHAOS_LLM_EXTRA_LATENCY_MS=$EXTRA_LATENCY_MS" >/dev/null
kube rollout status "deployment/$RELEASE-api" --timeout=5m >/dev/null
FAILURE_START=$(now)

sleep "$FAILURE_SECONDS"

FAILURE_END=$(now)
printf 'Removing the injected latency...\n'
kube set env "deployment/$RELEASE-api" CHAOS_ENABLED- CHAOS_LLM_EXTRA_LATENCY_MS- >/dev/null
kube rollout status "deployment/$RELEASE-api" --timeout=5m >/dev/null

sleep "$RECOVERY_SECONDS"
RECOVERY_END=$(now)

write_window incident-1 "$BASELINE_START" "$FAILURE_START" "$FAILURE_END" "$RECOVERY_END" \
    "Fixture generation delayed by ${EXTRA_LATENCY_MS}ms; LLM call p95 crosses its anomaly band."
