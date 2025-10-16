.PHONY: dev supabase resetdb prefect test

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

prefect:
	prefect server start

test:
	ruff check .
	mypy .
	$(PYTHON) -c "import agents.langgraph_chain as _mod; print('Loaded', _mod.__name__)"
