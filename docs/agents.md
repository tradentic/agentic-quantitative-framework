---
id: agents
title: Agents
---

# Agent Orchestration

Agents live in `agents/` and are orchestrated with LangGraph. The core planner
(`QuantitativePlanner`) stitches together three responsibilities:

1. **Feature ideation** — evaluate feature history and propose the next
   experiment using `propose_new_feature()`.
2. **Backtesting** — call `run_backtest()` to log deterministic metrics and
   extend the feature performance history.
3. **Vector memory maintenance** — coordinate `prune_vectors()` and
   `refresh_vector_store()` so the Supabase pgvector store stays lean.

Every node writes human-readable notes into the shared state so the resulting
plans are auditable. When adding new tools, ensure they are pure functions that
return serialisable data structures suitable for LangGraph checkpoints.
