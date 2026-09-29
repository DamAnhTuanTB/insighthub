# Day 7 AI work log

## Request

List what Day 7 still lacks, then complete the Day 7 work on a new branch.

## Accepted decisions

- Map specification section 11.3 to committed evidence in `showcase/README.md`,
  one row per required artifact, citing the file that proves it.
- Generate the weekly cost report with `scripts/day7/cost_report.py` from
  committed artifacts only. The script refuses to report zero AWS or provider
  cost when evidence records either being used.
- List costs no artifact records (Day 1 provider mode, coding host subscription,
  Slack/tunnel/GitHub plans) as unmeasured with a null amount.
- Draft the self-evaluation from the per-day rubric, including risks below L3
  (Day 3 IRSA/OIDC on the local profile, Day 2 quiz pending, Day 5 screencast).
- Write the Day 5 and Day 7 screencast scripts from actual bot and pipeline
  behavior (`scale api to 2` + `confirm <token>`, 60-second token, audit fields).
- Start the stack with `make up` and record `/healthz` 200 plus `make smoke` PASS
  on the ports configured in `.env`.

## Rejected decisions

- Do not record the Loom screencast, answer quizzes, choose the roadmap, or fill
  personal self-evaluation answers on the owner's behalf.
- Do not claim L4 where the rubric asks for evidence that does not exist:
  full OWASP Top 10 coverage, cost-per-success reduction, K8s production bot,
  Grafana Sift.
- Do not estimate subscription or AWS figures; do not present Day 6 declared
  chargeback rates as a provider invoice.

## Evidence regeneration (2026-09-29)

- Committed the Day 7 source first so every day binds to one fingerprint
  (`0a291d14…`), then reran each day before touching its envelope: Day 1 live
  verifier; Day 2 MCP tests, SDK probe, Codex host probe, debug lab; Day 3 a new
  GitHub Actions run (`36572814473`) whose provenance artifact replaced the
  deployment/binding files; Day 4 a full 70 minute baseline and three separate
  injections; Day 5 local pass; Day 6 full local pass (generator-written envelope).
- Envelopes for Day 1–5 have no generator; only `observed_at`, `source_sha256`
  and artifact hashes were refreshed, and only after the corresponding run passed.
- Rejected: reusing Day 4 RCA text from the first run. Claims with no collected
  sample were removed and every figure now comes from the new samples.
- Rejected: citing a band value collected before rule evaluation settled; the
  samples were recollected after the windows closed and the verifier re-queried
  all 36 citations.
- Rejected: editing the Makefile `verify-day7` target to add CI arguments after
  evidence was generated, because that would change the fingerprint; the full
  command is documented in `showcase/README.md` instead.
- Not redone: Day 2 Inspector screenshots, Day 2 quiz, Day 5 live Slack mentions —
  they need a person and the verifier does not read them.

## Review checklist

Rerun `python3 scripts/day7/cost_report.py` and confirm the total equals the Day 6
entries; open every path cited in `showcase/README.md`; check that submission
links resolve after merge; run `scripts/verify.py day7` and expect `INCOMPLETE`
with `full-project-review` until the human showcase items are submitted.
