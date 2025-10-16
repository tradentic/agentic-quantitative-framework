---
title: Agent Orchestration
description: How LangGraph memory, guardrails, and Supabase-backed tools coordinate autonomous research agents.
---

## Overview

The primary agent entry point is `agents/langgraph_chain.py`, which builds a LangGraph `StateGraph`
with an in-memory checkpointer (`MemorySaver`) so threads can be resumed or inspected. The module
exposes `build_planner()` and `run_planner()` helpers to make it easy to compile or execute the
planner from notebooks, CLI scripts, or Prefect tasks.

### State & Memory

- **Typed state** – `PlannerState` tracks the request payload, LangChain messages, guardrail paths,
  and long-term Supabase-backed state. The checkpointer stores a snapshot keyed by `thread_id` so
  reruns can resume after interruptions.
- **Long-term memory** – When an `agent_id` is provided, the planner hydrates state from the
  Supabase `agent_state` table via `framework.supabase_client.fetch_agent_state` and writes updates
  back with `persist_agent_state`.
- **Metrics tracking** – Tool results populate `PlannerState.metrics` and the Supabase record, giving
  downstream dashboards quick access to the latest Sharpe, pruning counts, or embedding refresh
  stats.

### Guardrails

After each tool call a guardrail node collects Python paths reported by the tool output
(`created_files`, `modified_files`, or explicit guardrail overrides) and runs `ruff` and `mypy` on
those files. Failing either check raises immediately, preventing the agent from suggesting changes
that would break CI. Additional paths can be injected through `state['guardrail_paths']`.

### Tooling Surface

The planner connects to four Supabase-first tools through LangGraph's `ToolNode`:

| Tool | Purpose | Supabase Integration |
| --- | --- | --- |
| `propose_new_feature` | Writes versioned modules under `features/` and upserts metadata into `feature_registry`. | `record_feature()` helper |
| `run_backtest` | Executes `backtest/engine.py`, uploads JSON + plots to Storage, inserts into `backtest_results`. | Storage uploads + `insert_backtest_result()` |
| `prune_vectors` | Calls the `rpc_prune_vectors` function to archive stale embeddings. | RPC in migrations |
| `refresh_vector_store` | Regenerates embeddings (TS2Vec) and upserts into `signal_embeddings`. | `insert_embeddings()` + `rpc_refresh_embeddings` |

Each tool returns a JSON-serialisable payload. The planner captures the payload, appends it to the
thread's history, and persists the most recent metrics to Supabase for auditability.

### Usage

```bash
python -c "from agents.langgraph_chain import run_planner; print(run_planner({'request': 'run backtest', 'payload': {'strategy_id': 'momentum-ts2vec-v1'}}))"
```

The example above runs the planner in a fresh `thread_id` and prints the resulting state. Prefect
flows and smoke tests use the same helper to exercise the durable planner during development.
