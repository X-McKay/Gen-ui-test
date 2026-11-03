# AI Governance Intake — developer entry points.
#
# Run `make` or `make help` for the list. Every target shells out to the same commands CI
# runs (see .github/workflows/ci.yml), so a green `make lint typecheck test check-schema`
# locally is a green pull request.

SHELL := /bin/sh
.DEFAULT_GOAL := help

BACKEND_DIR  := backend
FRONTEND_DIR := frontend

UV   ?= uv
PNPM ?= pnpm

# Ports and the URL the Next.js server uses to reach the backend (server-side only).
BACKEND_PORT ?= 8000
BACKEND_URL  ?= http://127.0.0.1:$(BACKEND_PORT)

# Extra arguments, e.g. `make test-backend PYTEST_ARGS="-k gdpr -x"`.
PYTEST_ARGS ?=
PLAYWRIGHT_ARGS ?=

# Prettier is only part of lint/format when the frontend carries a config file.
PRETTIER_CONFIG := $(wildcard $(FRONTEND_DIR)/.prettierrc*) $(wildcard $(FRONTEND_DIR)/prettier.config.*)

# Coverage: the rules engine must stay at 100 % (branch coverage on).
GOVERNANCE_COV := --cov=app/governance --cov-report=term-missing --cov-fail-under=100

.PHONY: help install dev dev-mock backend frontend lint format typecheck test test-backend \
        test-frontend export-schema check-schema e2e e2e-live e2e-ui build docker-up \
        docker-down clean

help: ## Show this help (default)
	@printf "\nAI Governance Intake — make targets\n\n"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nVariables: BACKEND_PORT=%s  BACKEND_URL=%s  PYTEST_ARGS=\"%s\"\n" "$(BACKEND_PORT)" "$(BACKEND_URL)" "$(PYTEST_ARGS)"
	@printf "Copy .env.example to .env (backend) and frontend/.env.local before 'make dev'.\n\n"

# ---- Setup ---------------------------------------------------------------------------------

install: ## Install backend (uv, dev extras), frontend (pnpm) and Playwright browsers
	cd $(BACKEND_DIR) && $(UV) sync --extra dev
	cd $(FRONTEND_DIR) && $(PNPM) install
	cd $(FRONTEND_DIR) && $(PNPM) exec playwright install chromium firefox webkit

# ---- Run -----------------------------------------------------------------------------------

# Both servers in one terminal (POSIX sh, no extra tooling). Ctrl-C reaches every process in
# the foreground group; the trap then sends TERM to the whole group so no uvicorn/next child
# survives, and the poll loop stops both servers when either one exits. $(1) = MOCK_MODEL.
define run_both
	@printf "backend  http://127.0.0.1:$(BACKEND_PORT)  (MOCK_MODEL=$(1))\nfrontend http://localhost:3000\n\n"
	@trap 'trap - INT TERM EXIT; kill 0 2>/dev/null' INT TERM EXIT; \
	( cd $(BACKEND_DIR) && MOCK_MODEL=$(1) exec $(UV) run uvicorn app.main:app --reload --reload-dir app --port $(BACKEND_PORT) ) & \
	backend_pid=$$!; \
	( cd $(FRONTEND_DIR) && BACKEND_URL=$(BACKEND_URL) exec $(PNPM) dev ) & \
	frontend_pid=$$!; \
	while kill -0 $$backend_pid 2>/dev/null && kill -0 $$frontend_pid 2>/dev/null; do sleep 1; done
endef

dev: ## Run backend and frontend with hot reload against the live model endpoint
	$(call run_both,0)

dev-mock: ## Same as dev, with MOCK_MODEL=1 (deterministic scripted model, no network)
	$(call run_both,1)

backend: ## Run only the backend (uvicorn --reload on $(BACKEND_PORT))
	cd $(BACKEND_DIR) && $(UV) run uvicorn app.main:app --reload --reload-dir app --port $(BACKEND_PORT)

frontend: ## Run only the frontend (next dev on 3000, BACKEND_URL=$(BACKEND_URL))
	cd $(FRONTEND_DIR) && BACKEND_URL=$(BACKEND_URL) $(PNPM) dev

# ---- Quality -------------------------------------------------------------------------------

lint: ## ruff format --check, ruff check, eslint (and prettier --check when configured)
	cd $(BACKEND_DIR) && $(UV) run ruff format --check .
	cd $(BACKEND_DIR) && $(UV) run ruff check .
	cd $(FRONTEND_DIR) && $(PNPM) lint
ifneq ($(strip $(PRETTIER_CONFIG)),)
	cd $(FRONTEND_DIR) && $(PNPM) format:check
endif

format: ## ruff format + ruff --fix (and prettier --write when configured)
	cd $(BACKEND_DIR) && $(UV) run ruff format .
	cd $(BACKEND_DIR) && $(UV) run ruff check --fix .
ifneq ($(strip $(PRETTIER_CONFIG)),)
	cd $(FRONTEND_DIR) && $(PNPM) format
endif

typecheck: ## mypy --strict on backend/app, tsc --noEmit on the frontend
	cd $(BACKEND_DIR) && $(UV) run mypy app
	cd $(FRONTEND_DIR) && $(PNPM) typecheck

test: test-backend test-frontend ## Backend tests (governance 100 % gate) + frontend unit tests

test-backend: ## pytest with coverage; fails below 100 % on app/governance
	cd $(BACKEND_DIR) && $(UV) run pytest $(GOVERNANCE_COV) $(PYTEST_ARGS)

test-frontend: ## vitest (passes when there are no unit tests yet)
	cd $(FRONTEND_DIR) && $(PNPM) test --passWithNoTests

# ---- Schema --------------------------------------------------------------------------------

export-schema: ## Regenerate schema/intake.schema.json and frontend/lib/intakeTypes.ts
	cd $(BACKEND_DIR) && PYTHONPATH=. $(UV) run python scripts/export_schema.py
	cd $(FRONTEND_DIR) && $(PNPM) gen:types

check-schema: ## Fail when the JSON schema or the generated TS types are stale
	cd $(BACKEND_DIR) && PYTHONPATH=. $(UV) run python scripts/export_schema.py --check
	cd $(FRONTEND_DIR) && $(PNPM) gen:types
	git diff --exit-code -- $(FRONTEND_DIR)/lib/intakeTypes.ts schema/intake.schema.json

# ---- End to end ----------------------------------------------------------------------------

e2e: ## Playwright suite against the scripted model (MOCK_MODEL=1)
	cd $(FRONTEND_DIR) && $(PNPM) exec playwright test $(PLAYWRIGHT_ARGS)

e2e-live: ## Playwright suite against the live model endpoint (E2E_LIVE=1)
	cd $(FRONTEND_DIR) && E2E_LIVE=1 $(PNPM) exec playwright test $(PLAYWRIGHT_ARGS)

e2e-ui: ## Playwright UI mode
	cd $(FRONTEND_DIR) && $(PNPM) exec playwright test --ui $(PLAYWRIGHT_ARGS)

# ---- Build and containers ------------------------------------------------------------------

build: ## Production build of the frontend (next build)
	cd $(FRONTEND_DIR) && $(PNPM) build

docker-up: ## Build and start backend + frontend with docker compose (needs .env)
	docker compose up --build -d
	@printf "\nfrontend http://localhost:3000\nbackend  http://localhost:8000/healthz\n"

docker-down: ## Stop the compose stack (keeps the sqlite volume)
	docker compose down

clean: ## Remove caches, coverage, build output and test reports (keeps .venv/node_modules)
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.mypy_cache $(BACKEND_DIR)/.ruff_cache \
	       $(BACKEND_DIR)/htmlcov $(BACKEND_DIR)/.coverage
	find $(BACKEND_DIR) -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf $(FRONTEND_DIR)/.next $(FRONTEND_DIR)/out $(FRONTEND_DIR)/test-results \
	       $(FRONTEND_DIR)/playwright-report $(FRONTEND_DIR)/blob-report $(FRONTEND_DIR)/tsconfig.tsbuildinfo
