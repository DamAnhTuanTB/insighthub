#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if [[ ! -f tmp/day6/runtime.env ]]; then
  echo "Day 6 runtime was not initialized."
  exit 0
fi

# Preserve all named volumes, model downloads, database spend, and evidence inputs.
docker compose --env-file tmp/day6/runtime.env -f docker-compose.yml -f docker-compose.day6.yml --profile ollama down
