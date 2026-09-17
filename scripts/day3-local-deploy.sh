#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
NAMESPACE=${NAMESPACE:-insighthub-dev}
RELEASE=${RELEASE:-insighthub}
KUBECONFIG_PATH=${KUBECONFIG_PATH:-${KUBECONFIG:-$HOME/.kube/config}}

require_tool() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Missing required tool: %s\n' "$1" >&2
        exit 2
    fi
}

for tool in docker helm kubectl openssl terraform; do
    require_tool "$tool"
done

KUBE_CONTEXT=${KUBE_CONTEXT:-$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context 2>/dev/null || true)}
if [ -z "$KUBE_CONTEXT" ]; then
    printf '%s\n' 'No active Kubernetes context. Configure KUBE_CONTEXT or kubeconfig first.' >&2
    exit 2
fi

kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" cluster-info >/dev/null

terraform -chdir="$REPO_ROOT/infra" init -input=false -reconfigure
terraform -chdir="$REPO_ROOT/infra" apply -input=false -auto-approve \
    -var="kube_context=$KUBE_CONTEXT" \
    -var="kubeconfig_path=$KUBECONFIG_PATH" \
    -var="namespace=$NAMESPACE"

docker build -t insighthub-api:local "$REPO_ROOT/api"
docker build -t insighthub-web:local "$REPO_ROOT/web"
docker build -t insighthub-worker:local -f "$REPO_ROOT/ingestion-worker/Dockerfile" "$REPO_ROOT"

case "$KUBE_CONTEXT" in
    kind-*)
        require_tool kind
        CLUSTER_NAME=${KUBE_CONTEXT#kind-}
        kind load docker-image --name "$CLUSTER_NAME" insighthub-api:local insighthub-web:local insighthub-worker:local
        ;;
    k3d-*)
        require_tool k3d
        CLUSTER_NAME=${KUBE_CONTEXT#k3d-}
        k3d image import --cluster "$CLUSTER_NAME" insighthub-api:local insighthub-web:local insighthub-worker:local
        ;;
    docker-desktop|orbstack)
        # These contexts normally share or import from the local Docker image store.
        ;;
    *)
        if [ "${ALLOW_SHARED_DOCKER_IMAGES:-0}" != "1" ]; then
            printf 'Unknown image-loading strategy for context %s.\n' "$KUBE_CONTEXT" >&2
            printf '%s\n' 'Load the three :local images into the cluster, then rerun with ALLOW_SHARED_DOCKER_IMAGES=1.' >&2
            exit 2
        fi
        ;;
esac

if ! kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" get secret runtime >/dev/null 2>&1; then
    DB_PASSWORD=$(openssl rand -hex 24)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    SECRET_DIR=$(mktemp -d "${TMPDIR:-/tmp}/insighthub-day3-secret.XXXXXX")
    SECRET_FILE="$SECRET_DIR/runtime.env"
    cleanup_secret_file() {
        rm -f "$SECRET_FILE"
        rmdir "$SECRET_DIR" 2>/dev/null || true
    }
    trap cleanup_secret_file EXIT INT TERM
    umask 077
    {
        printf 'POSTGRES_PASSWORD=%s\n' "$DB_PASSWORD"
        printf 'REDIS_PASSWORD=%s\n' "$REDIS_PASSWORD"
        printf 'DATABASE_URL=postgresql://insighthub:%s@%s-postgres:5432/insighthub\n' "$DB_PASSWORD" "$RELEASE"
        printf 'REDIS_URL=redis://:%s@%s-redis:6379/0\n' "$REDIS_PASSWORD" "$RELEASE"
    } > "$SECRET_FILE"
    kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" create secret generic runtime \
        --from-env-file="$SECRET_FILE" --dry-run=client -o yaml \
        | kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" apply -f -
    cleanup_secret_file
    trap - EXIT INT TERM
fi

kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" create configmap db-init \
    --from-file=init.sql="$REPO_ROOT/infra/db/init.sql" --dry-run=client -o yaml \
    | kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" apply -f -

helm upgrade --install "$RELEASE" "$REPO_ROOT/infra/helm/insighthub" \
    --kubeconfig "$KUBECONFIG_PATH" \
    --kube-context "$KUBE_CONTEXT" \
    --namespace "$NAMESPACE" \
    --values "$REPO_ROOT/infra/helm/insighthub/values-local.yaml" \
    --set-string "namespace=$NAMESPACE" \
    --rollback-on-failure --cleanup-on-fail --wait --timeout 8m

for workload in web api worker; do
    kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" rollout status \
        "deployment/$RELEASE-$workload" --timeout=5m
done
for dependency in postgres redis; do
    kubectl --kubeconfig "$KUBECONFIG_PATH" --context "$KUBE_CONTEXT" -n "$NAMESPACE" rollout status \
        "statefulset/$RELEASE-$dependency" --timeout=5m
done

printf '%s\n' 'Local deployment is ready. Run: make day3-local-smoke'
