# Changelog

## 2025-10-17

- Finalized the durable LangGraph planner with ToolNode orchestration, Supabase checkpointer hydration, and guardrailed tool execution.
- Codified Supabase schema, RPCs, triggers, and seed data through timestamped migrations with Prefect-aligned datasets.
- Documented Prefect local workflows, Supabase CLI usage, and end-to-end agent instructions across docs and local setup guides.

## 2025-10-16

- Adopted Prefect-based orchestration flows for embeddings, backtests, and pruning defined in `prefect.yaml`.
- Enhanced `agents/langgraph_chain.py` with Supabase-backed memory, tool metrics, and static-analysis guardrails.
- Added typed Supabase helpers, pgvector schema migrations, and documentation updates covering Prefect workflows.
