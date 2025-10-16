# Agentic Quantitative Framework

Supabase-first reference implementation for LangGraph-powered quantitative research agents. The framework coordinates GPT planners, Supabase pgvector storage, and strategy-specific modules to discover and maintain financial signals.

## Highlights

- **LangGraph agent chain** – `agents/langgraph_chain.py` orchestrates tool calls for feature proposals, backtesting, vector pruning, and embedding refreshes.
- **Supabase tooling** – `agents/tools.py` wraps Supabase RPCs/tables, and `features/generate_ts2vec_embeddings.py` writes embeddings to the `signal_embeddings` table.
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
   pnpm install  # if a frontend is present
   pip install -r requirements.txt  # or poetry install (define as needed)
   ```
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Start Supabase locally:
   ```bash
   supabase start
   ```
4. Validate the agent graph:
   ```bash
   python -c "from agents import build_langgraph_chain; build_langgraph_chain()"
   ```

Refer to [`LOCAL_DEV_SETUP.md`](LOCAL_DEV_SETUP.md) and the docs site (`docs/`) for deeper guidance.
