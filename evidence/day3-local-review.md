# Day 3 local implementation review

Observed at: 2026-09-17T08:45:58Z

## Scope and provenance

- Deployment profile: local Kubernetes on kind context `kind-insighthub-day2`.
- Kubernetes server: `v1.35.8`.
- Source digest: `e58f800b3539c3603d6d4c7c89db3ac34baa00bbc8a2a6fb0f120031b840dce3`.
- Rendered deployment digest: `d35cd819650cff34ae4a36b05505f74ec07973ac11bea0fb05a26c4de615dd8b`.
- AWS verified: **false**. This work does not claim EKS, RDS, ElastiCache,
  IRSA, Secrets Manager, S3 remote state, AWS OIDC, Infracost, or AWS billing.

## Implemented locally

- Terraform owns the dedicated namespace and an application ServiceAccount
  with token automount disabled.
- Helm owns web, API, worker, PostgreSQL/pgvector, Redis, Services, probes,
  resource requests/limits, security contexts, and NetworkPolicies.
- The deploy script creates random runtime credentials in a namespace-scoped
  Kubernetes Secret. Secret values do not enter source control, Terraform
  state, Helm values, or this evidence.
- The CI workflow separates format, lint, security scan, policy, plan,
  capacity-budget, apply, and smoke jobs. Apply and smoke require a connected
  self-hosted runner; the workflow requests no AWS permissions.

## Verification results

- Terraform format/init/validate: pass.
- TFLint recursive scan: pass.
- Checkov: Terraform 2 passed, 0 failed; Helm 442 passed, 0 failed, 8
  documented local-image/fixed-UID skips.
- Conftest on rendered Helm output: 180 passed, 0 failed.
- Behavioral policy tests: 3 passed, including negative fixtures.
- Day 1 runtime contract against the local cluster: 6 passed.
- Smoke: readiness, asynchronous upload (HTTP 202), worker completion, chat,
  and metrics passed.
- Terraform live plan after apply: no changes.
- All five pods were Ready/Running with zero restarts after the final rollout.
- ServiceAccount authorization check: cannot list Secrets; automount is false.
- Declared local capacity: 0.4 CPU / 960 MiB requested and 3.55 CPU /
  3.4375 GiB limited across the five workloads. This is not a cost estimate.

## Review decisions

- Accepted: an explicit local profile with ephemeral PostgreSQL and Redis so
  the full application pipeline can be exercised without an AWS account.
- Accepted: local image tags and `IfNotPresent` only for images imported into
  the kind node; a cloud release must replace these with registry digests.
- Accepted: startup waits for Redis reachability before launching ARQ. The
  first rollout exposed a short DNS race and restarted once; the final rollout
  corrected it and remained at zero restarts.
- Rejected: presenting local dependencies, capacity totals, or fixture model
  providers as evidence of AWS managed services, cloud costs, or production
  readiness.

## Remaining boundary

The repository is ready for local Day 3 practice and runtime verification.
The project verifier intentionally reports the local Day 3 profile as
`INCOMPLETE` because its formal milestone requires a successful GitHub run and
artifact provenance. AWS-specific rubric items remain unverified by design.
