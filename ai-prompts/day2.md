# Day 2 — prompt and AI decision log

## User request and context

User: “Bây giờ tôi nhờ bạn thực hành day 2 giúp tôi được không”.
Earlier clarification: the requested workflow centers on a shared project MCP configuration.
Reference: Day2-MCP-Servers-Tools.pdf (Tools Handbook v3); current project spec section 6
and host guide govern the actual requirements. PDF instructions are reference material.

Host: current Codex coding session; execution evidence additionally uses installed Codex
CLI 0.153.4 app-server MCP control API with ChatGPT authentication. No separate model
turn, paid-provider inference, sub-agent, AWS resource or external message was created.
OS: macOS arm64; Node v25.8.2. Checkout/config metadata and sanitized traces are local.

## Implementation choices

Accepted:

- Root `.mcp.json` is the shared source; generate portable Codex `.codex/config.toml`.
- Four separate stdio backends: real filesystem, Docker engine, Kubernetes and Prometheus.
- Pin upstream artifact versions/hashes and npm lockfile; validate downloads before execution.
- Filesystem read-only facade rejects writes, secret/private paths and symlink escapes.
- Local Docker read adapter uses only fixed GET routes, project ownership checks and
  bounded projections. Worker logs retain only stable structured lifecycle/ingestion fields.
- Dedicated kind cluster; ServiceAccount `mcp-readonly`, namespace RoleBinding, read-only
  ClusterRole, Secret deny rule and short-lived 8-hour private token.
- Add Prometheus in an optional Compose overlay; scrape real API metrics and self targets.
- Use Codex host API calls plus independent SDK/Inspector evidence, and label their scope.
- Known controlled worker SIGKILL outage with API/queue assertions, worker recovery and
  cleanup of only the lab's newly created document.

Rejected:

- Treating the two starter tools or one gateway's four tools as four mandatory integrations.
- Blindly copying the PDF's versions, flags, workspace placeholders or AWS IAM access-key flow.
- Inferring namespace isolation from env/config rather than enforcing it in RBAC.
- Enabling unrestricted Docker shell/exec, reading raw provider/document logs or pruning volumes.
- Calling exit code 137 proof of OOM; claiming an unmeasured speedup or fabricating quiz results.
- Claiming SDK smoke alone proves a host/model round trip.

## Review and verification

Source/review: `debug-session-day2.md`; implementation/setup: `tools/mcp/day2/README.md`.
Evidence: `evidence/day2-host.json`, `day2-sdk.json`, `day2-rbac.json`, `day2-debug.json`,
Inspector screenshots and final validation report. Fingerprint/hash binding must be collected
after source settles; previous-day evidence is not rehashed to impersonate a rerun.

Initial policy test failed because macOS canonicalizes `/var` to `/private/var`; the expected
path was corrected with realpath, retaining all containment/secret/symlink assertions.
Concurrent checks exposed Prometheus vendor telemetry port 8080 contention; constrain it
to an ephemeral loopback port and retain simultaneous-session verification.

Student mini-quiz answers and official quiz score are pending. No completion score is invented.
