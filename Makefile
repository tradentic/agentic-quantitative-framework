.PHONY: dev supabase resetdb seed prefect test lint typecheck

VENV ?= .venv
PYTHON ?= python3
PIP := $(VENV)/bin/pip
PYTHON_BIN := $(VENV)/bin/python

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .

.dev-ready: $(VENV)/bin/activate
	@touch $@

dev: .dev-ready
	@echo "Virtual environment ready at $(VENV)"

supabase:
	supabase start

resetdb:
	supabase db reset --local

seed: resetdb
	@echo "Seeds are applied automatically via supabase db reset --local."

prefect:
	prefect server start

lint:
	ruff check agents/langgraph_chain.py flows backtest features framework

typecheck:
	mypy agents/langgraph_chain.py flows backtest features framework

_import-check:
	$(PYTHON_BIN) -c "import agents.langgraph_chain"

test: lint typecheck _import-check
	@echo "Static validation complete."
