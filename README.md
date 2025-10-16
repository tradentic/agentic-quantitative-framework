# Agentic Quantitative Framework

Supabase-first reference implementation for LangGraph-powered quantitative research agents. The framework coordinates GPT planners, Supabase pgvector storage, and strategy-specific modules to discover and maintain financial signals.

## Highlights

- **LangGraph agent planner** – `agents/langgraph_chain.py` orchestrates tool calls for feature proposals, backtesting, vector pruning, and embedding refreshes with guardrailed static analysis.
- **Supabase tooling** – `agents/tools.py` wraps Supabase RPCs/tables, `framework/supabase_client.py` provides typed helpers, and `features/generate_ts2vec_embeddings.py` prepares pgvector rows.
- **Prefect orchestration** – `flows/` contains Prefect 2.x flows for embedding refreshes, scheduled backtests, and nightly vector pruning defined in `prefect.yaml`.
- **Use case modularity** – Add strategies under `use_cases/<name>/` with pipeline classes that build agent payloads.
- **Docusaurus docs** – Documentation lives in `docs/` and renders with the updated sidebar structure.

## Repository Layout

- `agents/` – LangGraph chain, Supabase tools, and compatibility wrappers.
- `features/` – Feature generation helpers that persist embeddings to Supabase.
- `use_cases/` – Strategy modules (for example, `insider_trading`) that integrate with the agent chain.
- `docs/` – Architecture references, ADRs, and operational guides.
- `framework/` – Shared Supabase client helpers for Python modules.

## Getting Started

1. Install dependencies via the devcontainer or manually:
   ```bash
   make dev  # creates a .venv and installs project dependencies
   ```
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Start Supabase locally:
   ```bash
   supabase start
   ```
4. Start the Prefect server and register deployments:
   ```bash
   prefect server start &
   prefect deployment apply prefect.yaml
   ```
5. Validate the agent planner:
   ```bash
   python -c "from agents import run_planner; print(run_planner({'request': 'refresh embeddings', 'payload': {'asset_symbol': 'AAPL', 'windows': []}}))"
   ```

Refer to [`LOCAL_DEV_SETUP.md`](LOCAL_DEV_SETUP.md) and the docs site (`docs/`) for deeper guidance.
