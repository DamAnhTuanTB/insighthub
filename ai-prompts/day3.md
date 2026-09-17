# Day 3 - Local IaC and Pipeline prompt log

## Request

Build Day 3 locally because no AWS account is available. Keep the implementation
honest about which AWS requirements are not verified.

## Accepted decisions

1. Use Terraform's Kubernetes provider only for the namespace and tokenless
   application ServiceAccount. This demonstrates IaC without placing runtime
   secrets in Terraform state.
2. Use Helm for web, API, worker, local PostgreSQL/pgvector, and Redis. The
   database/cache workloads are explicitly labelled local dependencies and do
   not count as RDS/ElastiCache evidence.
3. Reuse `infra/db/init.sql` through a runtime ConfigMap instead of copying the
   schema into the chart.
4. Generate local database/cache passwords during deployment and retain them
   only in a Kubernetes Secret.
5. Keep fixture providers as the default and retain the fail-closed real-provider
   behavior from Day 1.
6. Preserve 3-Layer Defense with TFLint, Checkov, Conftest, plan review, Helm
   policy checks, and manual local apply.
7. Replace cloud cost claims with a measurable Kubernetes resource budget that
   explicitly says it is not an AWS monetary estimate.

## Rejected decisions

1. Do not use LocalStack or MinIO and describe them as EKS/RDS/ElastiCache/S3
   verification; these would produce misleading evidence.
2. Do not put database passwords in committed Helm values, Terraform variables,
   workflow YAML, logs, or evidence.
3. Do not use a GitHub-hosted runner to pretend it can deploy into a laptop
   cluster. Manual deploy jobs require a labelled self-hosted runner.
4. Do not make PostgreSQL/Redis persistence look production-grade; the local lab
   is deliberately ephemeral and rebuildable.
5. Do not enable public ingress by default because the starter has no public
   authentication boundary.

## Review notes

- Handbook examples using Terraform 1.9/DynamoDB state locking were not copied.
  This local profile uses local state and pins Terraform >=1.10; an eventual AWS
  profile must use S3 native locking.
- AWS-only must-haves remain `not verified`, not silently removed from the
  original specification.
