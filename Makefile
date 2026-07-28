.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down logs restart test test-backend test-unit lint seed reset psql shell-api dev-api dev-web

help: ## Show the available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Build and start db + api + web, seeded and ready (http://localhost:5173)
	$(COMPOSE) up --build -d --wait
	@echo ""
	@echo "  Web UI   http://localhost:$${WEB_PORT:-5173}"
	@echo "  API docs http://localhost:$${API_PORT:-8000}/docs"
	@echo ""

down: ## Stop everything and delete the database volume
	$(COMPOSE) down -v

logs: ## Tail the API logs
	$(COMPOSE) logs -f api

restart: ## Rebuild and restart the API only
	$(COMPOSE) up -d --build api

test: ## Run the full backend suite (unit + API) against the compose database
	$(COMPOSE) up -d --wait db
	$(COMPOSE) run --rm --build --no-deps \
		-e DATABASE_URL=postgresql+asyncpg://tracker:tracker@db:5432/tracker_test \
		-e TEST_DATABASE_URL=postgresql+asyncpg://tracker:tracker@db:5432/tracker_test \
		api pytest

test-unit: ## Run only the state-machine unit tests (no database needed)
	$(COMPOSE) run --rm --build --no-deps api pytest tests/test_state_machine.py

lint: ## Ruff over the backend, tsc over the frontend
	$(COMPOSE) run --rm --no-deps api ruff check .
	cd frontend && npm run lint

seed: ## Re-run migrations, lifecycle sync and the CSV import
	$(COMPOSE) exec api python -m scripts.bootstrap

reset: ## Wipe the database and rebuild it from the CSV
	$(COMPOSE) down -v
	$(MAKE) up

psql: ## Open a psql shell on the demo database
	$(COMPOSE) exec db psql -U tracker -d tracker

shell-api: ## Shell into the API container
	$(COMPOSE) exec api sh

dev-api: ## Run the API on the host with reload (needs `make up` for the database)
	cd backend && DATABASE_URL=postgresql+asyncpg://tracker:tracker@localhost:5432/tracker \
		python -m scripts.bootstrap && \
		DATABASE_URL=postgresql+asyncpg://tracker:tracker@localhost:5432/tracker \
		uvicorn app.main:app --reload

dev-web: ## Run Vite against a locally running API
	cd frontend && npm install && npm run dev
