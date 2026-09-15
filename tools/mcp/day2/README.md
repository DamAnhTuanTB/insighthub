# InsightHub Day 2 — MCP lab

## Shared configuration

`.mcp.json` at the repository root is the shared source for four **separate stdio servers**:
Filesystem, Docker/container, Kubernetes and Prometheus. This lab does not change
InsightHub's upload/chat code. Each backend reads a real local system; no fixture
output is substituted for a failed tool call.

Codex uses the generated `.codex/config.toml`, not the JSON directly. After editing
the shared JSON, regenerate the Codex configuration from the repository root:

```sh
node tools/mcp/day2/host-config.mjs codex > .codex/config.toml
```

The portable configuration requires launching the host from the checkout root,
with Node on its PATH. For a GUI host with another working directory, generate
absolute paths **on that machine**, then merge the output into its existing config:

```sh
node tools/mcp/day2/host-config.mjs codex --absolute
```

Do not commit machine-specific output or overwrite unrelated user settings.
Codex project configuration must be trusted. Reload the host's MCP configuration
or open a new session after configuring servers. `codex mcp list` shows configured
servers, but a successful tool call is required to establish connection.

## Prepare local dependencies

Node >=22.19 and Python >=3.11; Docker and kubectl must already be available.
macOS/Linux arm64/amd64 executables are pinned with release URLs and SHA-256 hashes
in `artifacts.json`; npm dependencies are pinned in `package.json`/`package-lock.json`.
Downloads and credentials remain in ignored `tmp/day2/`.

```sh
npm ci --prefix tools/mcp --ignore-scripts
npm ci --prefix tools/mcp/day2 --ignore-scripts
python3 tools/mcp/day2/install.py
```

Versions: Filesystem upstream 2026.8.31 with local read-only policy facade 1.0.0;
Docker local adapter 1.0.0; Kubernetes MCP v0.0.66; Prometheus MCP v0.18.0;
Inspector 2.6.0; kind v0.33.0. The parent InsightHub starter remains separate.

## Prepare Kubernetes and Prometheus

Use a dedicated local cluster, not a production/admin kubeconfig in MCP. Create
the cluster only if `insighthub-day2` does not already exist:

```sh
tmp/day2/bin/kind create cluster --name insighthub-day2 \
  --config tools/mcp/day2/kind.yaml \
  --image kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0 \
  --kubeconfig tmp/day2/admin-kubeconfig.yaml --wait 120s
python3 tools/mcp/day2/setup_kubernetes.py
```

`setup_kubernetes.py` applies `rbac.yaml` and the explicitly labeled lab sample pod.
The read-only ClusterRole is bound by a **RoleBinding in insighthub**, so it grants
no access in other namespaces. Secrets, ConfigMaps, pods/exec and writes are absent.
The MCP server additionally uses `--read-only`, `--disable-multi-cluster`, core
toolsets and a Secret deny rule. Its private kubeconfig has mode 0600, one context,
one namespace and an 8-hour ServiceAccount token. Rerun the setup to refresh the
token and reload MCP. Do not put the admin kubeconfig or tokens in Git/evidence.

The Kubernetes pod is a real local **lab sample**, not a Day 3 InsightHub deployment.
Run the optional Prometheus overlay with the fixture LLM/provider mode explicit:

```sh
RAG_MODE=fixture LLM_PROVIDER=fixture EMBEDDING_PROVIDER=fixture \
  docker compose -f docker-compose.yml -f docker-compose.day2.yml up -d
```

Prometheus listens only on host loopback port 9090; it scrapes itself and the real
InsightHub API's `/metrics` at `api:8000` over Compose networking. This setup does
not add worker telemetry or complete Day 4. API/web host ports follow the project's
existing settings; discover them with `docker compose port api 8000` and
`docker compose port web 3000`. No AWS resources or paid model calls are required.

## Enforced read scope

| Backend | Enforcement | Host-visible tools |
|---|---|---|
| Filesystem | Project realpath containment; reject traversal/symlink escapes, private/cache directories and common secret files; 64 KiB file precheck | list_directory, read_text_file |
| Docker | Fixed HTTP GET routes on local Unix socket; enforce InsightHub Compose label and five services; project response fields; cap response/time; discard raw logs | docker_list_containers, docker_inspect_container, docker_worker_events |
| Kubernetes | Namespace RoleBinding, read-only ClusterRole, Secret deny rule and server read-only mode | pods_list_in_namespace, pods_get, pods_log, events_list |
| Prometheus | Dedicated local instance without admin/lifecycle flags; server tool allowlist excludes reload/quit/TSDB admin; 5s backend timeout | query |

MCP hints and host filters are additional controls, not RBAC. The operator owns
the source, config, Docker socket and cluster setup; these adapters do not protect
against an operator changing their code or configuration. Docker socket access is
privileged: use this trusted adapter only for the local lab. The server publishes
no exec/restart/kill tool and accepts no shell commands or arbitrary Docker routes.
Filesystem read-only is enforced by the facade; it never registers upstream write
tools. Common secret-name exclusions are not a general secret scanner for source
files. Use non-sensitive lab pods and do not pass production logs into MCP.

Prometheus upstream also registers core read tools internally; Codex filters to
`query`. Its telemetry listener uses an ephemeral loopback port so simultaneous
Inspector/host/SDK sessions do not contend for the vendor's default port 8080.
Its truncation option can be overridden by upstream tool arguments; it
is not a hard isolation guarantee. Only the dedicated non-sensitive lab instance
is in scope. Stdio servers run in the local trusted host, with no public MCP endpoint.

## Verify and collect evidence

```sh
npm --prefix tools/mcp test
npm --prefix tools/mcp/day2 test
node tools/mcp/day2/probe.mjs
python3 tools/mcp/day2/host_probe.py
```

`probe.mjs` collects official SDK tools/list, successful backend calls and direct
negative tools/call requests. `host_probe.py` uses the installed Codex app-server
API to initialize an ephemeral control session, inspect connection status and call
the tools through **Codex's MCP clients**. It never calls `turn/start`, starts model
inference or spawns a second AI agent. The root coding agent selects/interprets
these read-only calls. Evidence labels the API path and does not claim a separate
model-selection benchmark or a new interactive app session.

Inspector CLI can independently list/call each backend:

```sh
npm --prefix tools/mcp/day2 exec -- mcp-inspector --cli \
  --config .mcp.json --server kubernetes --cwd "$PWD" \
  --method tools/list --format json
npm --prefix tools/mcp/day2 exec -- mcp-inspector --cli \
  --config .mcp.json --server kubernetes --cwd "$PWD" \
  --method tools/call --tool-name pods_list_in_namespace \
  --tool-arg namespace=insighthub --format json
```

For UI evidence, start Inspector from the repo root, connect one backend at a time,
open Tools and execute a tool. Capture result + successful JSON-RPC tools/call.
Do not capture or save the Inspector session's auth token:

```sh
npm --prefix tools/mcp/day2 exec -- mcp-inspector --web --config .mcp.json --cwd "$PWD"
```

Run the controlled debug case **only while the local fixture worker is idle**:

```sh
python3 tools/mcp/day2/debug_lab.py
```

This deliberately force-stops only the worker, uses Docker MCP to inspect exit 137
and OOM state, verifies API availability/202 pending enqueue, restarts the worker,
awaits ready within 30 seconds and deletes only its newly created lab document.
It preserves volumes and resumes the worker on failure. Exit 137 is not sufficient
evidence of OOM; the injected cause is known and `oom_killed=false` is checked.

Raw traces/reports/screenshots live under ignored `evidence/day2-*`; the committed
review/debug summary is `debug-session-day2.md`. Check `quiz.md` and complete the
quiz yourself. Local quiz evidence is separate from any official trainer form.
Never mark Day 2 fully complete without the required quiz and review.

## Stop the lab without removing application volumes

```sh
docker compose -f docker-compose.yml -f docker-compose.day2.yml stop prometheus
docker stop insighthub-day2-control-plane
```

Stopping the cluster makes Kubernetes MCP unavailable. Resume it with
`docker start insighthub-day2-control-plane`; refresh the token if expired.
No `down -v`, Docker prune or cloud teardown is used.

Sources: [project spec section 6](../../../Running-Project-Specification-Student.md#6-day-2--mcp-protocol-integration),
[OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp),
[OpenAI app-server MCP API](https://learn.chatgpt.com/docs/app-server),
[Kubernetes MCP v0.0.66](https://github.com/containers/kubernetes-mcp-server/releases/tag/v0.0.66),
[Prometheus MCP v0.18.0](https://github.com/prometheus/prometheus-mcp/releases/tag/v0.18.0),
[kind v0.33.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0).
