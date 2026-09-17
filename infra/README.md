# Day 3 local IaC and Kubernetes deployment

This directory implements an explicit **local Kubernetes equivalent** of Day 3.
It does not claim EKS, RDS, ElastiCache, IRSA, Secrets Manager, AWS OIDC, S3
state, Infracost, or AWS billing verification.

## Ownership boundary

- Terraform: namespace and tokenless application ServiceAccount.
- Helm: web, API, ingestion worker, services, probes, resource budgets, optional
  ingress, and ephemeral local PostgreSQL/pgvector and Redis dependencies.
- Deploy script: runtime Secret and the ConfigMap created directly from
  `infra/db/init.sql`; secret values never enter Git, Terraform state, or Helm
  values.

PostgreSQL and Redis pods exist only for the local profile. They do not count as
proof of managed cloud database/cache services.

## Prerequisites

Install the versions pinned in `../.tool-versions`, plus Docker and `kubectl`.
The deploy script supports Docker Desktop/OrbStack directly and can import images
into kind or k3d when the corresponding CLI is installed.

Confirm the selected cluster before any mutation:

```bash
export KUBECONFIG_PATH="${KUBECONFIG_PATH:-$HOME/.kube/config}"
kubectl --kubeconfig "$KUBECONFIG_PATH" config get-contexts
kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context
kubectl --kubeconfig "$KUBECONFIG_PATH" cluster-info
kubectl --kubeconfig "$KUBECONFIG_PATH" get nodes
```

Do not point this local profile at a production cluster.

## Static gates

```bash
make day3-static
```

This runs Terraform format/init/validate, TFLint, Checkov, behavioral Conftest
tests, Helm lint/render, policy checks on the rendered chart, and a local
CPU/memory capacity report. The report is intentionally not a monetary or AWS
cost estimate.

## Deploy and verify

```bash
export KUBECONFIG_PATH="$PWD/tmp/day2/admin-kubeconfig.yaml" # if reusing the Day 2 kind lab
export KUBE_CONTEXT="$(kubectl --kubeconfig "$KUBECONFIG_PATH" config current-context)"
make day3-local-plan
make day3-local-up
make day3-local-smoke
```

The first deployment generates random local database/cache passwords and stores
them only in the `runtime` Kubernetes Secret inside the dedicated namespace.
Re-running the deploy reuses the existing Secret so an existing database is not
desynchronized.

Default access uses port-forward and does not expose the lab publicly. The smoke
script forwards the API to `127.0.0.1:18000` and web to `127.0.0.1:13000`, then
checks health, async upload, worker completion, chat, and metrics.

## Optional local TLS

Ingress is disabled because local clusters use different controllers. To enable
it, first install a trusted local ingress controller, create the TLS Secret
`insighthub-local-tls`, map `insighthub.local` to the controller address, and set:

```yaml
ingress:
  enabled: true
```

Never expose this starter publicly without an authentication boundary.

## Destroy

Local database/cache data uses `emptyDir` and is disposable. Destruction is
scoped to the selected namespace and requires an exact confirmation value:

```bash
CONFIRM_LOCAL_DESTROY=insighthub-dev make day3-local-down
```

No cluster-wide prune or volume deletion is performed.

## CI behavior

`.github/workflows/iac.yml` runs all static gates on GitHub-hosted runners. Its
manual `apply` and `smoke` jobs require a deliberately configured self-hosted
runner labelled `insighthub-local`; GitHub-hosted runners cannot access a cluster
on a laptop. No AWS permissions or long-lived cloud credentials are requested.
