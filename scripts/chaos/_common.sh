# Shared helpers for Day 4 fault injection. Sourced, not executed.
# Every script records its own baseline/failure/recovery window so RCA evidence
# cites a real interval instead of a guessed one.

NAMESPACE=${NAMESPACE:-insighthub-dev}
RELEASE=${RELEASE:-insighthub}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-${KUBECONFIG:-$HOME/.kube/config}}
KUBE_CONTEXT=${KUBE_CONTEXT:-$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context 2>/dev/null || true)}
OUTPUT_DIR=${OUTPUT_DIR:-tmp/day4}

kube() { kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" "$@"; }

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

guard_local_context() {
    case "$KUBE_CONTEXT" in
        kind-*|k3d-*|docker-desktop|orbstack) ;;
        *)
            printf 'Refusing to inject faults into non-local context %s.\n' "$KUBE_CONTEXT" >&2
            exit 2
            ;;
    esac
}

write_window() {
    # write_window <incident_id> <baseline_start> <failure_start> <failure_end> <recovery_end> <description>
    mkdir -p "$OUTPUT_DIR"
    python3 - "$@" <<'PY' > "$OUTPUT_DIR/$1.json"
import json, sys
incident, baseline, failure_start, failure_end, recovery_end, description = sys.argv[1:7]
print(json.dumps({
    "incident_id": incident,
    "baseline_start": baseline,
    "failure_start": failure_start,
    "failure_end": failure_end,
    "recovery_end": recovery_end,
    "description": description,
}, indent=2))
PY
    printf 'Window written: %s/%s.json\n' "$OUTPUT_DIR" "$1"
}
