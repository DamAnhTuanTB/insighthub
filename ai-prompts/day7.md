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

## Review checklist

Rerun `python3 scripts/day7/cost_report.py` and confirm the total equals the Day 6
entries; open every path cited in `showcase/README.md`; check that submission
links resolve after merge; run `scripts/verify.py day7` and expect `INCOMPLETE`
with `full-project-review` until the human showcase items are submitted.
