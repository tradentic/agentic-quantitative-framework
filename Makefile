.PHONY: dev supabase resetdb pushdb prefect lint test docs flows

VENV ?= .venv
PYTHON ?= python3
PIP := $(VENV)/bin/pip

$(VENV)/bin/activate:
$(PYTHON) -m venv $(VENV)
$(PIP) install --upgrade pip
$(PIP) install -e .

dev: $(VENV)/bin/activate
@echo "Virtual environment ready at $(VENV)"

supabase:
supabase start

resetdb:
supabase db reset --local

pushdb:
supabase db push --local

prefect:
prefect server start --host 127.0.0.1 --port 4200

lint: $(VENV)/bin/activate
$(VENV)/bin/ruff check .
$(VENV)/bin/mypy .

test: lint
$(VENV)/bin/pytest

docs:
pnpm --filter docs dev

flows:
prefect deployment apply prefect.yaml
