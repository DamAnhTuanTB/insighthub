#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

scripts/day6/up.sh

if [[ ! -x security/node_modules/.bin/promptfoo ]]; then
  npm ci --prefix security --ignore-scripts
fi

npm --prefix security run validate
python3 scripts/day6/run_promptfoo.py initial
python3 scripts/day6/evaluate.py \
  --phase initial \
  --target-url http://127.0.0.1:14000 \
  --output security/reports/eval-initial.json

python3 scripts/day6/run_promptfoo.py final
python3 scripts/day6/evaluate.py \
  --phase final \
  --target-url http://127.0.0.1:4001 \
  --output security/reports/eval-final.json \
  --cost-output security/reports/cost-report.json

python3 scripts/day6/live_e2e.py
mkdir -p tmp/day6
INSIGHTHUB_REPO_ROOT="$repo_root" \
INSIGHTHUB_VERIFY_RUN_ID="manual-day6" \
INSIGHTHUB_VERIFY_OBSERVATIONS="$repo_root/tmp/day6/manual-observations.json" \
DAY6_GATEWAY_URL=http://127.0.0.1:4001 \
DAY6_LITELLM_URL=http://127.0.0.1:14000 \
  .venv/bin/python -m pytest -c /dev/null -p no:cacheprovider tests/milestones/day6 -v

python3 scripts/day6/build_evidence.py
.venv/bin/python -B scripts/verify.py day6 \
  --evidence-dir evidence \
  --test-timeout 900 \
  --timeout 30
