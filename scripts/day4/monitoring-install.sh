#!/usr/bin/env bash
# Install kube-prometheus-stack into the local kind cluster.
# Local only: this is not Grafana Cloud and not an AWS managed service.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
NAMESPACE=${MONITORING_NAMESPACE:-monitoring}
RELEASE=${MONITORING_RELEASE:-kube-prom-stack}
CHART_VERSION=${MONITORING_CHART_VERSION:-91.4.1}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-${KUBECONFIG:-$HOME/.kube/config}}

for tool in helm kubectl openssl; do
    command -v "$tool" >/dev/null 2>&1 || { printf 'Missing required tool: %s\n' "$tool" >&2; exit 2; }
done

KUBE_CONTEXT=${KUBE_CONTEXT:-$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context 2>/dev/null || true)}
[ -n "$KUBE_CONTEXT" ] || { printf '%s\n' 'No active Kubernetes context.' >&2; exit 2; }

case "$KUBE_CONTEXT" in
    kind-*|k3d-*|docker-desktop|orbstack) ;;
    *)
        printf 'Refusing to install into non-local context %s.\n' "$KUBE_CONTEXT" >&2
        printf '%s\n' 'Set ALLOW_NONLOCAL_MONITORING=1 only for a cluster you own.' >&2
        [ "${ALLOW_NONLOCAL_MONITORING:-0}" = "1" ] || exit 2
        ;;
esac

kube() { kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" "$@"; }

kube create namespace "$NAMESPACE" --dry-run=client -o yaml | kube apply -f - >/dev/null

# Grafana admin credentials are generated locally and live only in the Secret.
if ! kube -n "$NAMESPACE" get secret grafana-admin >/dev/null 2>&1; then
    ADMIN_PASSWORD=$(openssl rand -base64 24)
    kube -n "$NAMESPACE" create secret generic grafana-admin \
        --from-literal=admin-user=admin \
        --from-literal=admin-password="$ADMIN_PASSWORD" \
        --dry-run=client -o yaml | kube -n "$NAMESPACE" apply -f - >/dev/null
    unset ADMIN_PASSWORD
    printf 'Generated a local Grafana admin password. Read it with:\n'
    printf '  kubectl -n %s get secret grafana-admin -o jsonpath="{.data.admin-password}" | base64 -d\n' "$NAMESPACE"
fi

# Alertmanager mounts this Secret; a placeholder keeps the pod healthy until the
# real webhook is supplied through scripts/day4/slack-secret.sh.
if ! kube -n "$NAMESPACE" get secret alertmanager-slack >/dev/null 2>&1; then
    kube -n "$NAMESPACE" create secret generic alertmanager-slack \
        --from-literal=webhook-url="https://hooks.slack.com/services/PENDING/PENDING/PENDING" \
        --dry-run=client -o yaml | kube -n "$NAMESPACE" apply -f - >/dev/null
    printf '%s\n' 'WARNING: Slack webhook is a placeholder. Delivery to #alerts is NOT verified.'
    printf '%s\n' 'Supply the real one: SLACK_WEBHOOK_URL=... scripts/day4/slack-secret.sh'
fi

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community >/dev/null

helm upgrade --install "$RELEASE" prometheus-community/kube-prometheus-stack \
    --version "$CHART_VERSION" \
    --kubeconfig "$KUBECONFIG_PATH" \
    --kube-context "$KUBE_CONTEXT" \
    --namespace "$NAMESPACE" \
    --values "$REPO_ROOT/observability/kube-prometheus-stack/values-local.yaml" \
    --wait --timeout 12m

printf '%s\n' 'Monitoring stack ready. Port-forward with: make day4-forward'
