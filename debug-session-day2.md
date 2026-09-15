# Day 2 — InsightHub MCP integration and debug review

## Environment and scope

- Observed: 2026-09-15, macOS arm64, Node v25.8.2, Codex CLI 0.153.4, ChatGPT auth.
- Shared config: `.mcp.json`; generated Codex project config: `.codex/config.toml`.
- Four separate local stdio processes, with pinned npm/release artifacts in `tools/mcp/day2`.
- Real local filesystem, Docker engine, kind cluster `insighthub-day2`, Prometheus and API.
- InsightHub LLM/embedding mode is explicitly **fixture**. No paid provider calls or AWS resources.
- API host port 8001; web 3001; Prometheus loopback 9090. The unrelated service on 8000 was not used as InsightHub evidence.
- Kubernetes `day2-lab-sample` is a real local sample pod, not a Day 3 application deployment.

## Backend/tool mapping and permissions

| Backend | Implementation/pin | Successful tool call | Enforced scope |
|---|---|---|---|
| Filesystem | upstream server-filesystem 2026.8.31 + local read-only facade 1.0.0 | list_directory; read_text_file | Realpath containment in checkout; reject secrets/private directories and writes |
| Docker/container | local Docker Engine GET adapter 1.0.0 | docker_list_containers; docker_inspect_container; docker_worker_events | InsightHub Compose project + five services; bounded projected metadata/events; no shell/mutation |
| Kubernetes | containers/kubernetes-mcp-server v0.0.66 | pods_list_in_namespace(insighthub) | Dedicated ServiceAccount, namespace RoleBinding, read-only ClusterRole, Secret denial, one context |
| Prometheus | prometheus/prometheus-mcp v0.18.0 | query(up) | Dedicated local instance; query reads; no lifecycle/TSDB admin tools |

`evidence/day2-host.json` records Codex host connection inventory, startup states and actual
`mcpServer/tool/call` input/output/timestamps. The root agent selected and interpreted the
calls through Codex's MCP clients. The host API control session was ephemeral and **no
model turn or additional AI agent was started**. This is not a claim that a separate model
autonomously discovered the tools or that the current GUI session has already reloaded them.

`evidence/day2-sdk.json` independently records official SDK tools/list/call and protocol
observed on initialize; SDK evidence is not substituted for host evidence. Inspector 2.6.0
UI connected to each backend and invoked a tool, with results and successful JSON-RPC:

- `evidence/day2-inspector-filesystem.png`
- `evidence/day2-inspector-docker.png`
- `evidence/day2-inspector-kubernetes.png`
- `evidence/day2-inspector-prometheus.png`

## Negative permission evidence

SDK direct tools/call requests verified:

- Filesystem: outside-checkout path, `.env` and write_file rejected.
- Docker: unrelated service and docker_exec rejected.
- Kubernetes: pods_delete, Secret read and kube-system pod list rejected.
- Prometheus: reload and delete_series rejected.

`evidence/day2-rbac.json` independently verifies the actual ServiceAccount:

| Request | Namespace | Result |
|---|---|---|
| get pods | insighthub | yes |
| delete pods | insighthub | no |
| get secrets | insighthub | no |
| get pods | kube-system | no |
| create pods/exec | insighthub | no |

Read-only hints/namespace strings in config are not the permission boundary. The role is
bound only in `insighthub`; the private short-lived kubeconfig is ignored and mode 0600.
Operators who can change trusted code/config retain their existing machine privileges.

## Case study — controlled worker outage

Incident: `day2-controlled-worker-outage`. Source/reproducer: `tools/mcp/day2/debug_lab.py`.
Raw sanitized MCP and HTTP observations: `evidence/day2-debug.json`.

1. Docker MCP confirmed worker running before the exercise.
2. The operator force-stopped only ingestion-worker using Compose timeout 0. This known
   SIGKILL injection creates an outage without deleting volumes or changing restart policy.
3. Docker MCP listed the five services and inspected worker state: stopped, exit code 137,
   `oom_killed=false`. The agent correctly attributed the failure to the controlled stop;
   exit 137 alone is insufficient evidence of an out-of-memory failure.
4. Docker MCP read only projected structured worker events; raw exception/provider logs
   were deliberately discarded by server code.
5. Prometheus MCP queried API target health; API liveness remained available. A bounded
   non-sensitive lab document upload returned **202 in 0.0146 seconds** and remained pending
   while the worker was stopped.
6. Restarting the worker resumed the queued job; it reached ready in **0.5225 seconds** after
   restart. Docker MCP observed the running worker and ingestion-completed event.
7. The script deleted only its newly uploaded lab document. The worker and all application
   services were restored; application volumes were preserved.

These are measurements for one local fixture-mode run, not a benchmark of manual vs AI
debugging or real-provider throughput. No manual baseline was measured.

## Review decisions and discovered issue

Accepted: share connection configuration at project level; generate Codex TOML from JSON;
keep credentials out of source; use role/token instead of a long-lived key; use a dedicated
lab cluster and namespace RoleBinding; expose a small read-only Docker adapter rather than
an unrestricted Docker exec tool; preserve the parent starter for independent compatibility tests.

Rejected handbook examples: unverified package/version/flags, unsupported workspace-variable
expansion, broad ClusterRoleBinding as namespace isolation, IAM user access keys, raw-log RCA,
Docker prune and the assertion that every exit 137 is OOM.

During simultaneous host/SDK/Inspector checks, the Prometheus vendor's default telemetry
listener on port 8080 caused process contention. The launcher now uses **127.0.0.1:0**:
each session gets an ephemeral loopback telemetry port. Retest simultaneous sessions before
accepting final evidence. Admin/lifecycle Prometheus features remain disabled.

## Validation and remaining submission

- Parent MCP suite: 22 passing, zero skipped; live starter smoke passes using API port 8001.
- Day 2 policy tests cover existing outside files, symlink escapes, secrets, cross-project
  Docker ownership changes and log canaries. No assertions were removed or skipped.
- Static host/context checker: PASS, four entries, no TODO; this checks structure only.
- Four real SDK/backend calls + negative calls; actual Codex host calls; Inspector UI calls;
  real RBAC checks; controlled debug and recovery.
- Quiz: **awaiting the student's answers** to `tools/mcp/day2/quiz.md`; official trainer quiz
  remains separate. Do not invent a score or mark the complete academic milestone passed.
- Source and the committed review summary are ready for pull request review; raw local
  evidence, downloaded executables and credentials remain ignored by Git.
- Source/config changes invalidate earlier fingerprint-bound evidence; regenerate evidence
  from actual reruns when submitting multiple days together, rather than copying new hashes.

Setup, refresh/reload, verification and non-destructive stop commands:
`tools/mcp/day2/README.md`. Source references: project specification section 6 and
`docs/Guide_Coding_Host_DO2603.md`; handbook PDF was treated as reference, not executable authorization.
