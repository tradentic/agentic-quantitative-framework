# Agent Task: Create a clean PR to finalize the Agentic Quantitative Framework

## GOAL
Produce a self-contained PR that:
1) Implements a durable **LangGraph** agent loop with tool calls.
2) Enforces **Supabase-first** architecture with **all DDL in timestamped migrations** (no ad-hoc SQL).
3) Adds **Prefect** for local orchestration and documents how to run it.
4) Keeps `.github/`, `.devcontainer/`, and `supabase/config.toml` unchanged (except minimal references/paths if needed).

## SOURCES OF TRUTH
- Architecture: `docs/architecture/quant_ai_strategy_design.md`
- Agent roles: `AGENTS.md`
- Local dev: `LOCAL_DEV_SETUP.md`

## HARD CONSTRAINTS
- ✅ Do **not** rename or delete `.github/` or `.devcontainer/` files.
- ✅ Do **not** modify `supabase/config.toml` (ports were customized manually).
- ✅ Prefer **Supabase** features over external deps (pgvector, Storage, Realtime/RPC).
- ✅ All docs must build in **Docusaurus** (valid frontmatter, working links).
- ✅ Migrations must have **14-digit** timestamp prefixes (`YYYYMMDDHHMMSS`).

---

## 1) LANGGRAPH AGENT (durable, tool-driven)
**Files:** `agents/langgraph_chain.py`, `agents/tools.py`, `agents/__init__.py`, optional `agents/gpt_feature_agent.py`

- Implement `langgraph_chain.py` using a `StateGraph` with a **checkpointer** (e.g., in-memory now; allow easy swap to SQLite/Redis later).
- Add a `ToolNode` that wires four tools from `agents/tools.py`:
  - `propose_new_feature(payload)` → creates/updates Python module(s) under `features/`, inserts row into `feature_registry`.
  - `run_backtest(config)` → calls `backtest/engine.py`; stores plots & JSON summary in Supabase Storage; inserts into `backtest_results`.
  - `prune_vectors(criteria)` → archives/deletes rows in `signal_embeddings` by policy; optional archive table `signal_embeddings_archive`.
  - `refresh_vector_store(job)` → recomputes embeddings (e.g., via `features/generate_ts2vec_embeddings.py`), bulk upserts into `signal_embeddings`.
- Export `build_planner()` and `run_planner(state: dict)` entry points and add a simple smoke test in comments.
- Guardrail: before committing agent-generated code, run `ruff` + `mypy` (CI already exists—only wire if missing).

**Notes for the agent:** use LangGraph checkpointers for persistence and ToolNode for tool calls.

---

## 2) SUPABASE: ALL DDL IN MIGRATIONS + SEEDS
**Folders:** `supabase/migrations/`, `supabase/seed.sql` (INSERTs only)

- Ensure **every** schema/helper change is in `supabase/migrations/` with **14-digit** timestamps:
  1. `*_setup_pgvector.sql`  
     - `create extension if not exists vector;`
  2. `*_baseline_schema.sql`  
     - Tables: `signal_embeddings`, `feature_registry`, `backtest_results`, `agent_state` (for long-term state), `signal_embeddings_archive` (optional).
     - Indexes:
       - `create index ... using ivfflat (embedding vector_cosine_ops) with (lists = 100);`
       - (COMMENT: For large data sets create IVFFlat after you have enough data; keep a reasonable default for local dev.)
  3. `*_rpc_refresh_embeddings.sql`  
     - `create or replace function public.rpc_refresh_embeddings(...) returns ... language plpgsql as $$ ... $$;`
  4. `*_rpc_prune_vectors.sql`  
     - `create or replace function public.rpc_prune_vectors(...) returns ...;`
  5. `*_signal_embedding_triggers.sql`  
     - `create or replace function ...` (trigger fn);
     - `drop trigger if exists ... on public.signal_embeddings;`
     - `create trigger ... after insert or update ... on public.signal_embeddings for each row execute function ...;`

- If older SQL duplicates exist under `supabase/sql/`, **move** them into the migration set above (idempotent statements) and remove any now-redundant `supabase/sql/*.sql` files.
- Confirm `supabase/seed.sql` contains **only** sample `INSERT`s (no DDL). Seed a tiny, coherent dataset:
  - `feature_registry`: one TS2Vec feature descriptor (name, version, params).
  - `signal_embeddings`: 1–3 small rows (vector(128) literals) with `asset_symbol`, `time_range`, `regime_tag`, `label`, `meta`.
  - `backtest_results`: 1 row with Sharpe/Sortino/drawdown and a fake artifact path.

**Remove any manual CLI steps** from docs (like `supabase db execute --file ...`); rely entirely on migrations + seeds.

---

## 3) PREFECT: LOCAL ORCHESTRATION
**Folder:** `flows/` (new)

- Add three flows:
  - `flows/embedding_flow.py` → new windows → compute embeddings → upsert to `signal_embeddings`.
  - `flows/backtest_flow.py` → scheduled backtests → artifacts to Storage → row in `backtest_results`.
  - `flows/prune_flow.py` → periodic pruning via `rpc_prune_vectors`.
- Add minimal local instructions:
  - `pip install prefect`
  - `prefect server start` (document default local URL & optional `PREFECT_API_URL`)
  - Run flows locally: `prefect run python -m flows.embedding_flow` (or register/deploy if you prefer)
- Keep this local-only (no Prefect Cloud setup).

---

## 4) DOCS (Docusaurus): VALID, LINKED, AND BUILDABLE
- Validate these docs exist with correct frontmatter and links:
  - `docs/architecture/quant_ai_strategy_design.md`
  - `docs/agents.md` (explain LangGraph tools + Supabase usage)
  - `docs/backtesting.md` (explain outputs to Storage + `backtest_results`)
  - `docs/deployment.md` (devcontainer, Supabase CLI, Prefect local)
  - `docs/use_cases/README.md` with link to insider trading doc
- Fix any dead links / missing frontmatter so the docs build cleanly.

---

## 5) LOCAL DEV SETUP (update `LOCAL_DEV_SETUP.md`)
- **Supabase CLI**:
  - `supabase start`
  - Local reset & seed: `supabase db reset --local`
  - Local dry run push: `supabase db push --local --dry-run`
  - (If linked) Remote dry run: `supabase db push --linked --dry-run`
  - Clarify that **reset** recreates the local DB, applies **all migrations**, then runs `supabase/seed.sql`.
- **Prefect**:
  - Install & run local server: `prefect server start`
  - Optional: `export PREFECT_API_URL=http://127.0.0.1:4200/api`
  - Run flows: `prefect run python -m flows.embedding_flow` (and friends)
- **Agent smoke test**:
  - `python -c "from agents.langgraph_chain import run_planner; print(run_planner({'hello':'world'}))"`

---

## 6) DX POLISH
- Ensure deps include (via `requirements.txt` or `pyproject.toml`):  
  `langgraph`, `openai`, `pydantic`, `prefect`, `supabase`, `pgvector`, `ruff`, `mypy`, `pandas`, `numpy`, `scikit-learn`, `matplotlib`
- Add/update `Makefile` targets:
  - `make dev` (venv + install)
  - `make supabase` (`supabase start`)
  - `make resetdb` (`supabase db reset --local`)
  - `make prefect` (`prefect server start`)
  - `make test` (`ruff` + `mypy` + import smoke test of `agents/langgraph_chain.py`)

---

## 7) ADRs
Add/confirm ADRs under `docs/architecture/adr/`:
- `0001-use-supabase-for-local-stack.md`
- `0002-use-supabase-as-vector-db.md`
- `0003-use-prefect-for-orchestration.md` (new):  
  **Decision:** Prefer Prefect for local orchestrations due to simple Pythonic flows and easy local server; revisit Airflow/Dagster later if needed.

---

## 8) VERIFICATION (automate in PR description)
1. `supabase start`  
2. `supabase db reset --local` (applies all migrations + seeds)  
3. Check objects via psql: extension `vector`, tables (`signal_embeddings`, `feature_registry`, `backtest_results`, `agent_state`, `signal_embeddings_archive`), RPCs (`rpc_refresh_embeddings`, `rpc_prune_vectors`), and triggers on `signal_embeddings`.  
4. `prefect server start` + run one flow locally.  
5. Build docs (ensure no frontmatter/link errors).  
6. Agent smoke test returns a dict.

---

## OUTPUT
- Open a PR named: **“LangGraph durability + Supabase migrations + Prefect local flows (clean reset)”**  
- PR should contain only the required changes above and a short CHANGELOG entry.
