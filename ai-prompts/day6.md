# Day 6 AI work log

## Request

Complete Day 6 to a locally passing state, test the live E2E path thoroughly,
then commit and open a pull request. Slack was already connected in Day 4/5.

## Accepted decisions

- Use real local Ollama inference through LiteLLM instead of fabricating provider
  evidence or spending money on a hosted provider.
- Give LiteLLM its required PostgreSQL store and three budgeted virtual keys for
  InsightHub, ChatOps, and coding workflows.
- Put a fail-closed guardrail in front of LiteLLM and route both chat and
  embeddings through the same authenticated gateway boundary.
- Compare initial and final scans on the identical 62-case dataset; include
  direct/indirect injection, retrieved poisoning, PII, excessive agency, and
  benign regression.
- Prove RAG poisoning through actual upload, worker ingestion, retrieval, and
  generation rather than treating a chat-only prompt as equivalent evidence.
- Attribute local compute with declared internal token rates and cgroup resource
  measurement; do not claim fabricated provider billing.

## Rejected decisions

- Do not use fixture/hash models for real-mode evidence.
- Do not silently enable Promptfoo hosted generation or send project purpose and
  prompts to a remote service.
- Do not reuse direct provider keys or expose virtual keys in Compose, reports,
  logs, shell output, or Git.
- Do not delete existing project volumes; Day 6 gets isolated app data volumes
  and teardown preserves them.
- Do not claim the local profile proves AWS Budgets, Bedrock Guardrails, or
  production network isolation.

## Review checklist

Review the diff for prompt/content/key logging, run Promptfoo validation, run the
live initial/final scans, verify all three workload traces and actual budget
denial, inspect the poisoned retrieval assertion, and rerun `scripts/verify.py
day6` only after the source fingerprint is settled.
