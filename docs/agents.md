---
id: agents
title: Agent Orchestration
description: How LangGraph and Supabase-powered tools coordinate autonomous research agents.
---

## Agent Topology

Agents live inside `agents/langgraph_chain.py`. The chain builds a `StateGraph` that:

1. Parses the incoming request or conversation history to determine the desired intent.
2. Routes to one of four Supabase-backed tools: `propose_new_feature`, `run_backtest`, `prune_vectors`, or `refresh_vector_store`.
3. Reflects on the tool response and records the result in agent state for downstream use.

Each node in the graph is deterministic, while the planner can optionally call GPT models (via `langchain_openai`) for nuanced routing. The chain is safe to invoke from background workers, webhooks, or CLI utilities because tool execution is idempotent and persists all results to Supabase.

## Supported Tools

| Tool | Purpose | Supabase Integration |
| --- | --- | --- |
| `propose_new_feature` | Inserts feature proposals into `feature_proposals` table | Supabase table insert |
| `run_backtest` | Executes the `run_strategy_backtest` RPC | Supabase RPC |
| `prune_vectors` | Removes stale embeddings | Supabase RPC (`prune_signal_embeddings`) |
| `refresh_vector_store` | Regenerates embeddings and refreshes pgvector indexes | Supabase RPC (`refresh_signal_embeddings`) |

Tool payloads can be authored by humans or generated programmatically by use case pipelines.

## Agent Inputs

Agents accept an `AgentState` object with:

- `task_context.intent` – the high-level action to perform.
- `task_context.payload` – arguments passed to the tool.
- `messages` – optional chat history if the planner should reason over conversation text.

Use the helper in `use_cases/base.py` to wrap payloads for each strategy.

## Extending the Chain

1. Implement a new tool in `agents/tools.py` that calls a Supabase RPC or table.
2. Register the tool in `TOOL_REGISTRY` inside `agents/langgraph_chain.py`.
3. Update documentation and use cases to surface the new capability.

All new tools should emit structured dictionaries so the planner and downstream systems can process results uniformly.
