#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
NAMESPACE=${NAMESPACE:-insighthub-dev}
RELEASE=${RELEASE:-insighthub}
API_PORT=${DAY3_API_PORT:-18000}
WEB_PORT=${DAY3_WEB_PORT:-13000}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-${KUBECONFIG:-$HOME/.kube/config}}
KUBE_CONTEXT=${KUBE_CONTEXT:-$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context 2>/dev/null || true)}

if [ -z "$KUBE_CONTEXT" ]; then
    printf '%s\n' 'No active Kubernetes context.' >&2
    exit 2
fi

SMOKE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/insighthub-day3-smoke.XXXXXX")
cleanup() {
    if [ -n "${API_FORWARD_PID:-}" ]; then kill "$API_FORWARD_PID" 2>/dev/null || true; fi
    if [ -n "${WEB_FORWARD_PID:-}" ]; then kill "$WEB_FORWARD_PID" 2>/dev/null || true; fi
    rm -f "$SMOKE_DIR/api.log" "$SMOKE_DIR/web.log"
    rmdir "$SMOKE_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" port-forward \
    "service/$RELEASE-api" "$API_PORT:8000" >"$SMOKE_DIR/api.log" 2>&1 &
API_FORWARD_PID=$!
kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" port-forward \
    "service/$RELEASE-web" "$WEB_PORT:3000" >"$SMOKE_DIR/web.log" 2>&1 &
WEB_FORWARD_PID=$!

READY=0
for _ in $(seq 1 30); do
    if curl --fail --silent --max-time 2 "http://127.0.0.1:$API_PORT/readyz" >/dev/null \
        && curl --fail --silent --max-time 2 "http://127.0.0.1:$WEB_PORT/api/health" >/dev/null; then
        READY=1
        break
    fi
    sleep 1
done
if [ "$READY" != "1" ]; then
    printf '%s\n' 'Port-forwarded services did not become ready.' >&2
    exit 1
fi

PYTHON_BIN=${PYTHON_BIN:-python3}
cd "$REPO_ROOT"
"$PYTHON_BIN" -B scripts/verify.py smoke \
    --api-url "http://127.0.0.1:$API_PORT" \
    --web-url "http://127.0.0.1:$WEB_PORT" \
    --poll-timeout 30 \
    --max-upload-seconds 1 \
    --json
