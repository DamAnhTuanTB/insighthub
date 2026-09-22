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

.PHONY: up down test test-backend test-worker test-verifiers test-mcp test-day1 verify-day1 smoke tools build ci worker-logs day3-fmt day3-init day3-validate day3-lint day3-scan day3-policy day3-render day3-budget day3-static day3-local-plan day3-local-up day3-local-smoke day3-local-down day4-monitoring-up day4-app-up day4-rules day4-dashboard day4-slack day4-loadgen-up day4-loadgen-down day4-forward day4-stop-forward day4-status day4-incident-1 day4-incident-2 day4-incident-3 day4-samples day4-verify day4-down
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

# ---- Day 4: observability on the local kind cluster (never AWS) ----
MONITORING_NAMESPACE ?= monitoring
PROMETHEUS_URL ?= http://127.0.0.1:9090
day4-monitoring-up:
	KUBE_CONTEXT="$(KUBE_CONTEXT)" MONITORING_NAMESPACE="$(MONITORING_NAMESPACE)" scripts/day4/monitoring-install.sh
day4-app-up:
	NAMESPACE="$(NAMESPACE)" KUBE_CONTEXT="$(KUBE_CONTEXT)" HELM_EXTRA_VALUES="$(CURDIR)/infra/helm/insighthub/values-observability.yaml" scripts/day3-local-deploy.sh
day4-rules:
	promtool check rules observability/rules/day4-rules.yaml
	cd observability/rules && promtool test rules day4-rules_test.yaml
	mkdir -p tmp/day4
	$(VERIFY_PYTHON) scripts/day4/render-prometheusrule.py --namespace "$(MONITORING_NAMESPACE)" --output tmp/day4/prometheusrule.yaml
	kubectl apply -f tmp/day4/prometheusrule.yaml
day4-dashboard:
	KUBE_CONTEXT="$(KUBE_CONTEXT)" MONITORING_NAMESPACE="$(MONITORING_NAMESPACE)" scripts/day4/dashboard-apply.sh
day4-slack:
	KUBE_CONTEXT="$(KUBE_CONTEXT)" MONITORING_NAMESPACE="$(MONITORING_NAMESPACE)" scripts/day4/slack-secret.sh
day4-loadgen-up:
	kubectl -n "$(NAMESPACE)" create configmap insighthub-loadgen --from-file=loadgen.py=observability/loadgen/loadgen.py --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -f observability/loadgen/loadgen.yaml
	kubectl -n "$(NAMESPACE)" rollout status deployment/insighthub-loadgen --timeout=5m
day4-loadgen-down:
	kubectl -n "$(NAMESPACE)" delete deployment insighthub-loadgen --ignore-not-found
day4-forward:
	scripts/day4/forward.sh start
day4-stop-forward:
	scripts/day4/forward.sh stop
day4-status:
	scripts/day4/status.sh
day4-incident-1:
	NAMESPACE="$(NAMESPACE)" KUBE_CONTEXT="$(KUBE_CONTEXT)" scripts/chaos/inject-llm-latency.sh
day4-incident-2:
	NAMESPACE="$(NAMESPACE)" KUBE_CONTEXT="$(KUBE_CONTEXT)" scripts/chaos/inject-queue-backlog.sh
day4-incident-3:
	NAMESPACE="$(NAMESPACE)" KUBE_CONTEXT="$(KUBE_CONTEXT)" scripts/chaos/inject-error-burst.sh
day4-samples:
	for n in 1 2 3; do \
		$(PYTHON) scripts/day4/collect-samples.py --window tmp/day4/incident-$$n.json --prometheus-url "$(PROMETHEUS_URL)" --output tmp/day4/incident-$$n-samples.json; \
	done
day4-verify:
	$(VERIFY_PYTHON) -B scripts/verify.py day4 --evidence-dir evidence --prometheus-url "$(PROMETHEUS_URL)"
day4-down:
	helm uninstall kube-prom-stack --namespace "$(MONITORING_NAMESPACE)" || true
	kubectl delete namespace "$(MONITORING_NAMESPACE)" --ignore-not-found
test: test-verifiers test-backend test-worker test-mcp
smoke:
	$(PYTHON) scripts/verify.py smoke --api-url "$(API_URL)" --web-url "$(WEB_URL)"
ci:
	$(MAKE) up
	$(MAKE) test
	$(MAKE) smoke
# CI callers must always run down (also on failure). Volumes are preserved here.
