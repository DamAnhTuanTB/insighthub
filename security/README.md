# Day 6: Security, Governance, and FinOps

This local profile runs a real model path without paid APIs: InsightHub routes
through the guardrail service, LiteLLM, and Ollama (`qwen2.5:0.5b` plus
`mxbai-embed-large`). LiteLLM uses PostgreSQL so virtual-key spend and budget
denials are enforced rather than simulated.

## One-command local verification

```bash
make day6-local-pass
```

The command starts the isolated Day 6 databases, verifies 62 fixed cases before
and after guardrails, runs pinned Promptfoo for the same cases, uploads and
retrieves a poisoned document, checks a benign RAG query, exercises InsightHub,
ChatOps and coding virtual keys, proves budget denial, and runs the repository
Day 6 verifier. Model and database volumes are preserved by `make day6-down`.

Runtime credentials live only in ignored `tmp/day6/runtime.env` and
`tmp/day6/keys.json` with mode `0600`. Reports and audit logs never contain the
keys. The content-free JSON audit is in ignored `tmp/day6/audit/audit.jsonl`.

Useful endpoints while the profile is up:

- InsightHub: `http://127.0.0.1:13000` and API `:8000`
- LiteLLM: `http://127.0.0.1:14000/health/liveliness`
- Guardrail: `http://127.0.0.1:4001/healthz` and `/metrics`

## Evaluation interpretation

`red-team-initial.*` calls LiteLLM directly and is expected to show open attack
assertions. `red-team-final.*` calls the guardrail and must pass every case. The
normalized `eval-initial.json`, `eval-final.json`, and `cost-report.json` bind to
the repository fingerprint and are consumed by `scripts/verify.py day6`.

The local Ollama provider has no invoice. The cost report therefore declares a
fixed internal chargeback rate of $1/M input tokens and $2/M output tokens. A
zero-token guardrail denial includes measured container cgroup duration and peak
memory instead of claiming that local computation is free.

Promptfoo generation plugins can require hosted remote inference. This profile
does not opt into remote generation; it keeps the valid pinned plugin/strategy
configuration and executes the committed 62-case dataset locally. See
`coverage.md` for the exact mapping.

The workload trace uses the ChatOps key to synthesize a response from bounded
tool context and the coding key to review an explicit context/diff/test tuple.
The InsightHub key is exercised by the real upload, embedding, retrieval, and
chat pipeline.

## Teardown

```bash
make day6-down
```

This stops containers without deleting volumes. No AWS resources are used, so
the conditional AWS Budgets acceptance item does not apply.
