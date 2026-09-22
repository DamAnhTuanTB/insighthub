#!/usr/bin/env bash
# Port-forward the Day 4 endpoints. Everything stays bound to loopback.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
NAMESPACE=${NAMESPACE:-insighthub-dev}
MONITORING_NAMESPACE=${MONITORING_NAMESPACE:-monitoring}
PID_DIR="$REPO_ROOT/tmp/day4"
LOG_DIR="$PID_DIR"

start_one() {
    # start_one <name> <namespace> <service> <local:remote>
    local name=$1 namespace=$2 service=$3 ports=$4
    local pidfile="$PID_DIR/pf-$name.pid"
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        printf '%-12s already running (pid %s)\n' "$name" "$(cat "$pidfile")"
        return
    fi
    kubectl port-forward -n "$namespace" "svc/$service" "$ports" \
        > "$LOG_DIR/pf-$name.log" 2>&1 &
    echo $! > "$pidfile"
    printf '%-12s %s -> %s\n' "$name" "$service" "$ports"
}

stop_all() {
    for pidfile in "$PID_DIR"/pf-*.pid; do
        [ -e "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            printf 'stopped %s (pid %s)\n' "$(basename "$pidfile" .pid)" "$pid"
        fi
        rm -f "$pidfile"
    done
}

mkdir -p "$PID_DIR"
case "${1:-start}" in
    start)
        start_one prometheus "$MONITORING_NAMESPACE" kube-prom-stack-prometheus 9090:9090
        start_one grafana "$MONITORING_NAMESPACE" kube-prom-stack-grafana 3001:80
        start_one alertmanager "$MONITORING_NAMESPACE" kube-prom-stack-alertmanager 9093:9093
        start_one api "$NAMESPACE" insighthub-api 18000:8000
        printf '\nPrometheus http://127.0.0.1:9090 · Grafana http://127.0.0.1:3001 · Alertmanager http://127.0.0.1:9093 · API http://127.0.0.1:18000\n'
        printf 'Grafana password: kubectl -n %s get secret grafana-admin -o jsonpath="{.data.admin-password}" | base64 -d\n' "$MONITORING_NAMESPACE"
        ;;
    stop) stop_all ;;
    *) printf 'Usage: %s [start|stop]\n' "$0" >&2; exit 2 ;;
esac
