COMPOSE ?= docker compose
PYTHON ?= python3
VERIFY_PYTHON ?= .venv/bin/python
NPM ?= npm
NODE ?= node
API_URL ?= http://localhost:8000
WEB_URL ?= http://localhost:3000

.PHONY: up down test test-backend test-worker test-verifiers test-mcp test-day1 verify-day1 smoke tools build ci worker-logs
up:
	$(COMPOSE) up --build -d --wait
down:
	$(COMPOSE) --profile ollama down
build:
	$(COMPOSE) build
tools:
	$(NPM) ci --prefix tools/mcp --ignore-scripts
test-verifiers:
	$(PYTHON) -m unittest discover -s tests -p 'test_verify*.py' -v
test-backend:
	$(COMPOSE) run --rm --no-deps -e RUN_DB_TESTS=1 -e TEST_SCHEMA_PATH=/tmp/init.sql -v "$(CURDIR)/infra/db/init.sql:/tmp/init.sql:ro" api python -m unittest discover -s tests -v
test-worker:
	$(COMPOSE) run --rm --no-deps ingestion-worker python -m unittest discover -s tests -v
test-mcp:
	$(NPM) --prefix tools/mcp test
	$(NODE) tools/mcp/smoke.mjs
test-day1:
	$(VERIFY_PYTHON) -m pytest -c /dev/null -p no:cacheprovider tests/milestones/day1 -v
verify-day1:
	$(VERIFY_PYTHON) -B scripts/verify.py day1 --evidence-dir evidence --api-url "$(API_URL)" --web-url "$(WEB_URL)"
worker-logs:
	$(COMPOSE) logs -f ingestion-worker
test: test-verifiers test-backend test-worker test-mcp
smoke:
	$(PYTHON) scripts/verify.py smoke --api-url "$(API_URL)" --web-url "$(WEB_URL)"
ci:
	$(MAKE) up
	$(MAKE) test
	$(MAKE) smoke
# CI callers must always run down (also on failure). Volumes are preserved here.
