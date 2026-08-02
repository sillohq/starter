# Every task this project needs, discoverable with `make` on its own.
#
# The commands are plain uvicorn/python/sillo-start invocations rather than
# anything bespoke, so you can always read what a target does and run it by
# hand when you need to vary it.

.DEFAULT_GOAL := help
.PHONY: help setup install migrate migration rollback history dev serve worker \
        scheduler admin test smoke lint format check clean up plan

PY  := uv run
APP := app.main:app
HOST ?= 127.0.0.1
PORT ?= 8000

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# -- setup -------------------------------------------------------------

setup: install ## Install dependencies, create .env, and set the database up
	@test -f .env || (cp .env.example .env && echo "  created .env — change the secrets before deploying")
	@$(MAKE) migrate
	@echo "  ready. run: make dev"

install:  ## Install Python dependencies, including the dev tools
	# --all-extras because a cloned starter is a development environment:
	# pytest, ruff and httpx are wanted from the first minute.
	uv sync --all-extras

# -- database ----------------------------------------------------------

# Migrations go through sillo.record, never the ORM's own tooling. The settings
# come from app/database.py, which is what the application runs on too.
MIGRATE := $(PY) python scripts/migrate.py

migrate:  ## Create the database and apply every pending migration
	$(MIGRATE) init

up:  ## Apply pending migrations, without writing any
	$(MIGRATE) up

migration:  ## Write a migration from model changes. make migration m="add_posts"
	$(MIGRATE) make "$(or $(m),update)"
	$(MIGRATE) up

rollback:  ## Roll back to a migration. make rollback to=0001_initial
	$(MIGRATE) down "$(to)"

plan:  ## Show which migrations would run
	$(MIGRATE) plan

admin:  ## Create an administrator account
	$(PY) python scripts/create_admin.py

# -- running -----------------------------------------------------------

dev:  ## Run the application with reload
	$(PY) uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

serve:  ## Run the application as it would run in production
	$(PY) uvicorn $(APP) --host 0.0.0.0 --port $(PORT) --workers 4

# Uncomment _register_work(application) in app/bootstrap.py before using these.
worker:  ## Run the queue worker
	$(PY) python scripts/worker.py

scheduler:  ## Run the scheduled task runner
	$(PY) python scripts/scheduler.py

# -- quality -----------------------------------------------------------

test:  ## Run the test suite
	$(PY) pytest -q

smoke:  ## Boot the app and call every route
	$(PY) python scripts/smoke.py

lint:  ## Check formatting and lint rules
	$(PY) ruff check .
	$(PY) ruff format --check .

format:  ## Apply formatting and fixable lint rules
	$(PY) ruff format .
	$(PY) ruff check --fix .

check: lint test smoke  ## Everything CI runs

clean:  ## Remove caches and build artefacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache dist build *.egg-info
