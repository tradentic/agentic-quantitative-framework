.PHONY: dev supabase docs flows test lint typecheck

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

docs:
pnpm --filter docs dev

flows:
prefect server start --host 0.0.0.0 & \
SERVER_PID=$$!; \
sleep 5; \
prefect deployment apply prefect.yaml; \
wait $$SERVER_PID

test:
ruff check .
mypy .
pytest

lint:
ruff check .

typecheck:
mypy .
