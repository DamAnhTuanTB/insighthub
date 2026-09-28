#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

python3 scripts/day6/bootstrap.py init
compose=(docker compose --env-file tmp/day6/runtime.env -f docker-compose.yml -f docker-compose.day6.yml --profile ollama)

"${compose[@]}" up -d --wait ollama litellm-db litellm
python3 scripts/day6/bootstrap.py keys
"${compose[@]}" up -d --build --wait postgres redis day6-postgres day6-redis ollama litellm-db litellm security-gateway api ingestion-worker web

echo "Day 6 local stack is healthy on web :13000, API :8000, LiteLLM :14000, guardrail :4001."
