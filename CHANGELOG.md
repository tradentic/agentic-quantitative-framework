# Changelog

## 2025-01-15

- Replaced the LangGraph agent chain with a durable planner exposing `build_planner()` and `run_planner()` backed by a ToolNode and Supabase-aware guardrails.
- Added a timestamped Supabase migration for `backtest_requests` along with refreshed seeds covering `backtest_results` and pending requests.
- Documented Prefect local orchestration commands, LangGraph smoke tests, and Supabase CLI workflows across `LOCAL_DEV_SETUP.md` and the docs site.

## 2025-10-16

- Adopted Prefect-based orchestration flows for embeddings, backtests, and pruning defined in `prefect.yaml`.
- Enhanced `agents/langgraph_chain.py` with Supabase-backed memory, tool metrics, and static-analysis guardrails.
- Added typed Supabase helpers, pgvector schema migrations, and documentation updates covering Prefect workflows.
