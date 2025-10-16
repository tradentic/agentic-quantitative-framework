# Agentic Quantitative Framework Strategy Design

This document captures the guiding principles behind the framework:

1. **Agentic Core** — LangGraph planners coordinate feature ideation, backtests,
   and vector maintenance. The shared state must remain serialisable and easy to
   audit.
2. **Vector Memory** — Supabase with pgvector stores engineered feature
   embeddings and performance traces. Drift monitoring feeds back into the
   planner via `prune_vectors()` and `refresh_vector_store()`.
3. **Feature Factory** — Modular scripts (TS2Vec, symbolic regression, etc.) live
   under `features/` and expose deterministic interfaces so agents can compose
   them safely.
4. **Evaluation Loop** — Backtest scenarios in `backtests/` produce metrics the
   planner can digest. Each scenario includes metadata for regime, horizon, and
   evaluation criteria.
5. **Use Case Portability** — `use_cases/` holds manifests describing data
   sources, labelling rules, and roll-out cadence. Agents rely on these manifests
   to pivot between strategies such as insider trading and earnings drift.

Keep this document updated when architecture decisions materially change the
agent loop or supporting infrastructure.
