#!/usr/bin/env bash
# Publish the dashboard to Grafana through the sidecar ConfigMap convention.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
NAMESPACE=${MONITORING_NAMESPACE:-monitoring}
DASHBOARD=${DASHBOARD_FILE:-$REPO_ROOT/observability/grafana/insighthub-overview.json}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-${KUBECONFIG:-$HOME/.kube/config}}
KUBE_CONTEXT=${KUBE_CONTEXT:-$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context)}

[ -f "$DASHBOARD" ] || { printf 'Dashboard not found: %s\n' "$DASHBOARD" >&2; exit 2; }

kube() { kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" "$@"; }

kube -n "$NAMESPACE" create configmap insighthub-dashboards \
    --from-file="insighthub-overview.json=$DASHBOARD" \
    --dry-run=client -o yaml \
    | kube label --local -f - grafana_dashboard=1 app.kubernetes.io/name=insighthub -o yaml \
    | kube apply -f - >/dev/null

printf 'Dashboard applied. Grafana sidecar picks it up within about a minute.\n'
