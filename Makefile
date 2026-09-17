COMPOSE ?= docker compose
PYTHON ?= python3
VERIFY_PYTHON ?= .venv/bin/python
NPM ?= npm
NODE ?= node
TERRAFORM ?= terraform
TFLINT ?= tflint
CHECKOV ?= checkov
CONFTEST ?= conftest
HELM ?= helm
API_URL ?= http://localhost:8000
WEB_URL ?= http://localhost:3000
NAMESPACE ?= insighthub-dev
KUBE_CONTEXT ?= $(shell kubectl config current-context 2>/dev/null)
KUBECONFIG_PATH ?= $(if $(KUBECONFIG),$(KUBECONFIG),$(HOME)/.kube/config)

.PHONY: up down test test-backend test-worker test-verifiers test-mcp test-day1 verify-day1 smoke tools build ci worker-logs day3-fmt day3-init day3-validate day3-lint day3-scan day3-policy day3-render day3-budget day3-static day3-local-plan day3-local-up day3-local-smoke day3-local-down
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
day3-fmt:
	$(TERRAFORM) -chdir=infra fmt -check -recursive
day3-init:
	$(TERRAFORM) -chdir=infra init -backend=false -input=false
day3-validate: day3-init
	$(TERRAFORM) -chdir=infra validate -no-color
day3-lint:
	cd infra && $(TFLINT) --init --config="$(CURDIR)/infra/.tflint.hcl"
	cd infra && $(TFLINT) --recursive --format compact --config="$(CURDIR)/infra/.tflint.hcl"
day3-scan:
	$(CHECKOV) -d infra --quiet
day3-policy:
	$(VERIFY_PYTHON) -m pytest -c /dev/null -p no:cacheprovider tests/milestones/day3 -v
day3-render:
	mkdir -p tmp/day3
	$(HELM) lint infra/helm/insighthub --values infra/helm/insighthub/values-local.yaml
	$(HELM) template insighthub infra/helm/insighthub --namespace "$(NAMESPACE)" --values infra/helm/insighthub/values-local.yaml > tmp/day3/rendered.yaml
	$(CONFTEST) test --policy infra/policy/kubernetes tmp/day3/rendered.yaml
day3-budget: day3-render
	$(VERIFY_PYTHON) scripts/day3_local_budget.py --manifest tmp/day3/rendered.yaml --output tmp/day3/local-budget.json
	$(PYTHON) -m json.tool tmp/day3/local-budget.json
day3-static: day3-fmt day3-validate day3-lint day3-scan day3-policy day3-budget
day3-local-plan:
	$(TERRAFORM) -chdir=infra init -input=false -reconfigure
	$(TERRAFORM) -chdir=infra plan -input=false -var="namespace=$(NAMESPACE)" -var="kube_context=$(KUBE_CONTEXT)" -var="kubeconfig_path=$(KUBECONFIG_PATH)"
day3-local-up:
	NAMESPACE="$(NAMESPACE)" scripts/day3-local-deploy.sh
day3-local-smoke:
	NAMESPACE="$(NAMESPACE)" PYTHON_BIN="$(PYTHON)" scripts/day3-local-smoke.sh
day3-local-down:
	NAMESPACE="$(NAMESPACE)" scripts/day3-local-destroy.sh
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
