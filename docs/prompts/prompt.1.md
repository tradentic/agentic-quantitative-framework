# Agent Task: Finalize Agentic Quantitative Framework (Enhancements + Prefect ADR)

## SOURCE OF TRUTH
- Architecture: `docs/architecture/quant_ai_strategy_design.md`
- Agent roles: `AGENTS.md`

## HARD CONSTRAINTS
- ✅ **Supabase-first:** use Supabase (pgvector, storage, realtime/RPC) where a feature exists
- ✅ **Do NOT rename/delete** anything in `.github/` or `.devcontainer/`
- ✅ **Do NOT modify** `supabase/config.toml` (ports were changed manually)
- ✅ All docs must load in Docusaurus (valid frontmatter, sidebar, links)

---

## 1) LANGGRAPH AGENT — IMPLEMENTATION DETAILS
- In `agents/langgraph_chain.py`:
  - Add explicit **state/memory** (short-term: last N tool calls & metrics; long-term: Supabase “stores” or a `state` table).
  - Ensure the four tools exist and are wired:
    - `propose_new_feature(payload)`: creates/edits Python in `features/`, versioned filenames, writes metadata row to Supabase `feature_registry`.
    - `run_backtest(config)`: runs `backtest/engine.py` with a config; uploads summary JSON + plots to Supabase storage; inserts results into `backtest_results`.
    - `prune_vectors(criteria)`: deletes/archives old or low-utility rows from `signal_embeddings` based on t-stat, recency, regime diversity.
    - `refresh_vector_store(embedding_job)`: recomputes embeddings via `features/generate_ts2vec_embeddings.py`; bulk upsert into `signal_embeddings`.
  - Add a **guardrail** step: validate that any agent-generated file passes `ruff` + `mypy` before commit suggestions.

## 2) SUPABASE — VECTORS / RPC / TRIGGERS
- Create/verify SQL:
  - `supabase/vector_db/setup_pgvector.sql`:
    - `signal_embeddings(id uuid pk, asset_symbol text, time_range tstzrange, embedding vector(128), regime_tag text, label jsonb, meta jsonb)`
    - IVFFLAT index w/ cosine ops; `lists` tuned for local dev.
  - `supabase/functions/`:
    - `rpc_refresh_embeddings.sql`: RPC stub that enqueues an “embedding refresh” job (for local dev, can be a table insert + realtime event).
    - `rpc_prune_vectors.sql`: RPC that archives rows by criteria to `signal_embeddings_archive`.
- Implement Python client `framework/supabase_client.py`:
  - typed helpers for `insert_embeddings`, `fetch_nearest`, `insert_backtest_result`, `list_failed_features`.
- Ensure `agents/tools.py` uses the above client (no direct raw HTTP scattered around).

## 3) PREFECT (NEW DECISION) — FLOWS & ADR
- Introduce **Prefect** as the workflow engine for local orchestration:
  - `flows/embedding_flow.py`: watch for new raw windows -> compute embeddings -> upsert to `signal_embeddings`.
  - `flows/backtest_flow.py`: run backtests on schedule or trigger -> write outputs to storage + DB.
  - `flows/prune_flow.py`: scheduled prune job using Supabase RPC.
- Add `prefect.yaml` & a minimal `README` snippet to run locally (`prefect server start`, `prefect deployment apply`).
- **Add ADR #0003** at `docs/architecture/adr/0003-use-prefect-for-orchestration.md`:
  - Context: compared Prefect vs. Airflow/Dagster; local-first, Pythonic, simple dev UX favored.
  - Decision: Prefect for event-driven, developer-friendly local orchestration; leave abstraction to switch later if needed.
  - Consequences: lightweight agent scheduling, simple retries, UI, logs; future option to promote to Prefect Cloud.

## 4) DOCUSAURUS — VALIDATION & LINKS
- Ensure `docs/` pages have valid frontmatter (`id`, `title`, optional `sidebar_position`).
- Add/verify:
  - `docs/agents.md`: links to `AGENTS.md` and explains LangGraph chain & tools.
  - `docs/backtesting.md`: explains how `run_backtest` writes to Supabase (tables + storage).
  - `docs/deployment.md`: devcontainer, Supabase CLI, Prefect local UI, and how to run flows.
- Confirm the architecture doc remains at `docs/architecture/quant_ai_strategy_design.md` and is linked in the sidebar.

## 5) DEV EXPERIENCE
- Add `pyproject.toml` (or `requirements.txt`) with: `langgraph`, `openai`, `pydantic`, `prefect`, `supabase`, `pgvector`, `ruff`, `mypy`, `pandas`, `numpy`, `matplotlib`, `scikit-learn`.
- Add `Makefile` tasks:
  - `make dev` (create venv, install deps)
  - `make supabase` (`supabase start`)
  - `make docs` (`pnpm --filter docs dev` OR your chosen docs cmd)
  - `make flows` (start Prefect server + run local deployments)
  - `make test` (ruff + mypy + pytest)
- Update `.env.example` with Prefect + Supabase vars; do not overwrite existing values.

## 6) CI / WORKFLOWS
- Do **not** delete or rename `.github` files; only adjust steps if necessary:
  - Ensure CI runs `ruff`, `mypy`, and a quick import check of `agents/langgraph_chain.py`.
  - Add a docs build job to ensure Docusaurus compiles.

## 7) FINAL SANITY PASS
- Verify that:
  - `agents/langgraph_chain.py` imports and initializes without errors.
  - Prefect flows can run locally (README snippets).
  - Docusaurus builds without broken links.
  - Supabase migrations apply cleanly; **do not touch** `supabase/config.toml`.

## OUTPUT
- Updated code, flows, and docs committed on a new branch.
- ADR `0003-use-prefect-for-orchestration.md` added and linked from `docs/deployment.md`.
- Short `CHANGELOG.md` entry describing the Prefect adoption and LangGraph enhancements.
