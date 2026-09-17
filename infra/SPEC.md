# InsightHub Day 3 - Local Kubernetes specification

## Intent

Run the complete InsightHub application on a local Kubernetes cluster without
claiming AWS verification. Terraform owns the namespace and least-privilege
service account. Helm owns the application workloads and the explicitly local
PostgreSQL/pgvector and Redis dependencies.

## Scope

- Target an existing local Kubernetes cluster selected by kubeconfig context.
- Create namespace `insighthub-dev` and service account `insighthub`.
- Deploy `web`, `api`, and `ingestion-worker` as separate workloads.
- Deploy PostgreSQL 16 with pgvector and Redis 7 as ephemeral local lab
  dependencies. They are not substitutes for managed RDS or ElastiCache proof.
- Reuse `infra/db/init.sql` as the single database schema source.
- Use fixture providers by default. Real provider mode must be selected
  explicitly and must receive credentials through the existing Secret.
- Expose the web application through port-forward by default. Ingress/TLS is an
  optional local overlay because ingress controllers differ between clusters.

## Constraints

- No AWS account, AWS credentials, long-lived cloud key, or fabricated cloud
  evidence.
- No secret values in Terraform state, Git, Helm values, logs, or evidence.
- API and worker receive identical database, Redis, provider, model, embedding
  dimension, and embedding revision settings.
- Images run as the non-root users already defined by their Dockerfiles.
- Every container has resource requests and limits; application containers use
  read-only root filesystems with writable `/tmp` mounts.
- Local data is disposable. Destroying the namespace removes the lab data.

## Required labels

Every Terraform-managed Kubernetes object has:

- `app.kubernetes.io/name=insighthub`
- `app.kubernetes.io/managed-by=terraform`
- `insighthub.dev/environment=dev`
- `insighthub.dev/owner=<owner>`
- `insighthub.dev/cost-center=learning`

Helm-managed objects use the same identity labels and
`app.kubernetes.io/managed-by=Helm`.

## Acceptance

1. `terraform fmt -check -recursive`, `terraform validate`, and `tflint` pass.
2. Checkov reports no blocking finding in `infra/`.
3. Conftest accepts safe Terraform/Kubernetes fixtures and rejects unsafe ones.
4. `helm lint` and `helm template` pass; rendered workloads pass Conftest.
5. Terraform creates only the selected namespace and service account.
6. Helm reports the web, API, worker, PostgreSQL, and Redis workloads Ready.
7. `/healthz`, upload `202`, ready-within-30-seconds, and `/chat` smoke checks
   pass against port-forwarded services.
8. Evidence says `deployment_profile=local-kubernetes` and
   `aws_verified=false`.

## Explicit non-goals

- EKS, RDS, ElastiCache, IRSA, Secrets Manager, AWS OIDC, S3 state, Infracost,
  or AWS cost verification.
- Production-grade persistence, high availability, public exposure, or public
  certificate issuance.
