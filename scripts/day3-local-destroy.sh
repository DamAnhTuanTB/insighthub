#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
NAMESPACE=${NAMESPACE:-insighthub-dev}
RELEASE=${RELEASE:-insighthub}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-${KUBECONFIG:-$HOME/.kube/config}}
KUBE_CONTEXT=${KUBE_CONTEXT:-$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context 2>/dev/null || true)}

if [ -z "$KUBE_CONTEXT" ]; then
    printf '%s\n' 'No active Kubernetes context.' >&2
    exit 2
fi
if [ "${CONFIRM_LOCAL_DESTROY:-}" != "$NAMESPACE" ]; then
    printf 'Refusing to delete. Set CONFIRM_LOCAL_DESTROY=%s to confirm this namespace.\n' "$NAMESPACE" >&2
    exit 2
fi

if helm --kubeconfig "$KUBECONFIG_PATH" --kube-context "$KUBE_CONTEXT" --namespace "$NAMESPACE" status "$RELEASE" >/dev/null 2>&1; then
    helm --kubeconfig "$KUBECONFIG_PATH" --kube-context "$KUBE_CONTEXT" --namespace "$NAMESPACE" uninstall "$RELEASE" --wait
fi
terraform -chdir="$REPO_ROOT/infra" destroy -input=false -auto-approve \
    -var="kube_context=$KUBE_CONTEXT" \
    -var="kubeconfig_path=$KUBECONFIG_PATH" \
    -var="namespace=$NAMESPACE"

printf 'Removed local InsightHub namespace %s. Data was ephemeral and is not recoverable.\n' "$NAMESPACE"
