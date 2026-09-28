# Day 6 evaluation coverage

The committed 62-case dataset is fixed across the initial and final runs so the
comparison measures the guardrail change rather than a different sample. It has
12 direct injection, 10 indirect injection, 10 RAG-poisoning, 10 PII, 10
excessive-agency, and 10 benign regression cases.

| Risk | Promptfoo configuration | Fixed live cases | Runtime control |
|---|---|---:|---|
| Direct prompt injection | `jailbreak-templates` strategy | 12 | input classifier + prompt boundary |
| Indirect prompt injection | `indirect-prompt-injection` | 10 | retrieved text is untrusted + input classifier |
| RAG poisoning | `rag-poisoning` | 10 plus upload/retrieve E2E | classifier after retrieval, before generation |
| PII disclosure | `pii:direct` | 10 | input and output PII classifiers |
| Excessive agency | `excessive-agency` | 10 | deny action language; Day 5 approval engine remains authoritative |
| Benign regression | authored fixed tests | 10 | allowed through to the real local model |

Promptfoo remote test generation is intentionally not used for the local-pass
profile because it would send the target purpose to a hosted generation service.
The checked-in cases are authored, reviewed, and executed by Promptfoo against
the live HTTP targets. The plugin IDs remain configured and pinned for an
operator who explicitly opts into generation.
