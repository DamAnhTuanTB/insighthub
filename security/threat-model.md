# InsightHub Day 6 threat model

Scope: document upload, background ingestion, vector retrieval, chat generation,
ChatOps/coding clients, the guardrail, LiteLLM, Ollama, and local spend storage.
Trust boundaries are the public web/API boundary, uploaded/retrieved content,
the guardrail-to-gateway hop, virtual-key identities, and the PostgreSQL stores.

| ID | Threat and abuse path | Impact | Preventive controls | Detection and verification | Residual risk |
|---|---|---|---|---|---|
| T1 | A user directly tells the model to ignore system instructions or reveal the prompt. | Policy bypass and prompt disclosure. | Input injection classifier, fixed system instruction hierarchy, bounded body. | Promptfoo direct cases and `test_injection_blocked`; decision metric/audit. | Novel paraphrases can evade regex; update cases from incidents. |
| T2 | A document contains instructions that execute only after retrieval. | Indirect injection affects otherwise benign users. | Documents remain untrusted, and the assembled post-retrieval message is scanned immediately before generation. | Live E2E uploads the poisoned document, proves it was retrieved, and checks the standard denial. | Obfuscated multilingual attacks need broader classifiers. |
| T3 | An attacker poisons the vector corpus to dominate retrieval. | Persistent manipulation and denial of useful answers. | Authenticated ingestion boundary, embedding identity, ready-only retrieval, source display, post-retrieval scan. | RAG-poisoning cases plus retrieved-source assertion. | Similarity manipulation without instruction text can still lower quality. |
| T4 | PII enters a prompt or appears in a model response. | Privacy breach and unauthorized retention. | PII checks on input and output; audit excludes content; public errors are sanitized. | Email, phone, payment, SSN, and Vietnamese identity cases. | Context-dependent names and uncommon identifiers may not match patterns. |
| T5 | Model text requests shell, cluster, or destructive action without approval. | Excessive agency and infrastructure damage. | Guardrail denies action language; Day 5 permission tiers and confirmation tokens remain the action authority. | Excessive-agency cases and Day 5 approval tests. | Safe natural-language discussions must avoid false positives; no model output directly invokes tools. |
| T6 | A leaked key bypasses attribution or spends without bound. | Bill shock and loss of accountability. | Three distinct LiteLLM virtual keys, model allowlists, per-key budgets/RPM/TPM/parallel limits, PostgreSQL spend. | Three workload traces, key aliases, and an allowed-then-denied budget test. | One request can overshoot a very small cap before asynchronous spend is recorded. |
| T7 | A client bypasses the guardrail and calls a provider directly. | All content controls can be skipped. | InsightHub accepts `LITELLM_API_KEY`, its base URL is the guardrail, and no paid-provider key is present in the Day 6 profile. Network policy is required outside local Compose. | Audit proves app calls at the guardrail; config tests assert key precedence. | Local host users can reach the explicitly published baseline on host port 14000; production needs private networking. |
| T8 | Logs or evidence capture prompts, documents, keys, or raw exceptions. | Secret/content disclosure through observability. | Content-free bounded audit schema; ignored 0600 secrets; sanitized upstream errors; no provider bodies. | Review audit fields and repository secret scan before commit. | Container operators can inspect process environment; production requires a secret manager. |
| T9 | A database/cache outage causes budget or auth enforcement to fail open. | Requests run without reliable spend enforcement. | LiteLLM uses PostgreSQL; virtual keys cannot authenticate without it; guardrail returns a sanitized denial on upstream failure. | Stop/dependency health behavior and LiteLLM budget contract. | Already cached auth can persist briefly; production should enable fail-closed distributed controls. |
| T10 | Oversized input or high concurrency exhausts CPU/memory on the local model. | Availability loss and denial of wallet/compute. | 256 KiB gateway request cap, API upload cap, per-key RPM/TPM/parallel limits, model output cap, container memory limits. | Metrics expose request decisions/tokens/cost; load thresholds are dashboarded. | Compose limits are single-host and not a substitute for production autoscaling. |

## Defense in depth

The six runtime layers are request validation, input classification, prompt/data
separation, LiteLLM identity/budget policy, output classification, and
content-free audit/metrics. A denial at any layer is terminal; fallback never
bypasses guardrails. The local profile deliberately has no provider fallback.

## Data and key lifecycle

Uploaded test documents use an isolated Day 6 PostgreSQL volume. The poisoned
document is deleted immediately after its retrieval assertion; the benign test
document is retained as reproducible pipeline evidence. Virtual keys and the
master/salt key remain in ignored local files and are never committed. `down`
preserves data; operators may remove only the named Day 6 volumes separately
after reviewing their contents.
