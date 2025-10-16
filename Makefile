.PHONY: dev supabase resetdb pushdb prefect lint test docs flows

VENV ?= .venv
PYTHON ?= python3
PIP := $(VENV)/bin/pip

$(VENV)/bin/activate:
$(PYTHON) -m venv $(VENV)
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
	prefect server start

lint:
	ruff check .
	mypy agents features framework flows backtest

test: lint
	python -c "from agents.langgraph_chain import build_planner; build_planner()"

docs:
	pnpm --filter docs dev

flows:
	prefect deployment apply prefect.yaml
