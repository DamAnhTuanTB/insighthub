#!/usr/bin/env bash
# Store the Slack incoming webhook as a namespace-scoped Secret.
# The URL is read from the environment and is never echoed, committed, or
# written into Helm values, Terraform state, logs, or evidence.
set -eu

NAMESPACE=${MONITORING_NAMESPACE:-monitoring}
SECRET=${SLACK_SECRET_NAME:-alertmanager-slack}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-${KUBECONFIG:-$HOME/.kube/config}}
KUBE_CONTEXT=${KUBE_CONTEXT:-$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context)}

if [ -z "${SLACK_WEBHOOK_URL:-}" ]; then
    printf '%s\n' 'SLACK_WEBHOOK_URL is not set.' >&2
    printf '%s\n' 'Run: SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." scripts/day4/slack-secret.sh' >&2
    exit 2
fi

case "$SLACK_WEBHOOK_URL" in
    https://hooks.slack.com/services/*) ;;
    *)
        printf '%s\n' 'Refusing: value is not a Slack incoming webhook URL.' >&2
        exit 2
        ;;
esac

kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" \
    create namespace "$NAMESPACE" --dry-run=client -o yaml \
    | kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" apply -f - >/dev/null

SECRET_DIR=$(mktemp -d "${TMPDIR:-/tmp}/insighthub-day4-slack.XXXXXX")
SECRET_FILE="$SECRET_DIR/webhook-url"
cleanup() {
    rm -f "$SECRET_FILE"
    rmdir "$SECRET_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
umask 077
printf '%s' "$SLACK_WEBHOOK_URL" > "$SECRET_FILE"

kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" \
    create secret generic "$SECRET" --from-file=webhook-url="$SECRET_FILE" \
    --dry-run=client -o yaml \
    | kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" apply -f - >/dev/null

printf 'Secret %s/%s updated. The URL was not printed.\n' "$NAMESPACE" "$SECRET"
