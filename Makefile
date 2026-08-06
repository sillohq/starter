# Every task this project needs, discoverable with `make` on its own.
#
# The commands are plain uvicorn/python/sillo-start invocations rather than
# anything bespoke, so you can always read what a target does and run it by
# hand when you need to vary it.

.DEFAULT_GOAL := help
.PHONY: help setup install migrate migration plan rollback admin users \
        dev serve worker scheduler test smoke lint format check clean

PY  := uv run
APP := app.main:app
HOST ?= 127.0.0.1
PORT ?= 8000

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# -- setup -------------------------------------------------------------

# The placeholder key is replaced rather than copied: a starter whose
# SECRET_KEY is the same in every clone is a starter that signs every
# deployment's sessions with a published secret.
setup: install ## Install dependencies, create .env, and set the database up
	@test -f .env || (cp .env.example .env \
	  && $(PY) python -c "import pathlib, secrets; p = pathlib.Path('.env'); p.write_text(p.read_text().replace('generate-me', secrets.token_urlsafe(48)))" \
	  && echo "  created .env with a fresh SECRET_KEY")
	@$(MAKE) migrate
	@echo "  ready. run: make dev"

# --all-extras because a cloned starter is a development environment:
# pytest, ruff and httpx are wanted from the first minute.
install:  ## Install Python dependencies, including the dev tools
	uv sync --all-extras

# -- database ----------------------------------------------------------

# Everything goes through the `sillo` command, which finds the application and
# derives its commands from it: the database manager and scheduler it set up,
# the user model it authenticates against, and whatever this project registers
# with app.add_command. There is no console file to maintain.
CONSOLE := $(PY) sillo

# The bootstrap on the first line is what makes this work on a fresh clone,
# where there is no migration to apply yet. It only runs when the migrations
# package is empty, so a later `make migrate` never writes one behind your back.
migrate:  ## Create the database and apply every pending migration
	@ls database/migrations/0*.py >/dev/null 2>&1 || ($(CONSOLE) db:init && $(CONSOLE) db:make initial)
	$(CONSOLE) db:migrate

migration:  ## Write a migration and apply it. make migration m="add_posts"
	$(CONSOLE) db:make "$(or $(m),update)" --apply

plan:  ## Show which migrations would run
	$(CONSOLE) db:plan

rollback:  ## Roll back to a migration. make rollback to=0001_initial
	@test -n "$(to)" || (echo "  need a target: make rollback to=0001_initial"; exit 1)
	$(CONSOLE) db:rollback "$(to)"

# Guarded, because the console would otherwise be handed empty strings and
# report a validation failure that says nothing about the missing argument.
admin:  ## Create an administrator account. make admin e=ada@x.com u=ada
	@test -n "$(e)" -a -n "$(u)" || (echo "  need both: make admin e=ada@x.com u=ada"; exit 1)
	$(CONSOLE) user:admin "$(e)" "$(u)"

users:  ## List users
	$(CONSOLE) user:list

# -- running -----------------------------------------------------------

dev:  ## Run the application with reload
	$(CONSOLE) serve --reload --host $(HOST) --port $(PORT)

serve:  ## Run the application as it would run in production
	$(PY) uvicorn $(APP) --host 0.0.0.0 --port $(PORT) --workers 4

# Uncomment _register_work(application) in app/bootstrap.py before using these.
worker:  ## Run the queue worker
	$(CONSOLE) queue:work

scheduler:  ## Run the scheduled task runner
	$(CONSOLE) schedule:run

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
