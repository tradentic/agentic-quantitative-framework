---
id: architecture-quant-ai-strategy-design
title: Quant AI Strategy Design
sidebar_position: 1
description: Supabase-first reference architecture for the Agentic Quantitative Framework.
slug: /architecture/quant_ai_strategy_design
---

## Overview

The Agentic Quantitative Framework orchestrates GPT-native research agents, Supabase services, and LangGraph workflows to discover and maintain predictive financial signals. The design emphasizes:

- **Supabase-unified storage** for relational data, pgvector embeddings, file artifacts, and realtime triggers.
- **LangGraph state machines** that coordinate long-running GPT interactions with deterministic tool execution.
- **Use case modularity**, allowing each strategy under `use_cases/<name>/` to define its own labeling, features, and evaluation loops while sharing the same infrastructure.

## Layered Architecture

### 1. Infrastructure

| Component | Technology |
| --- | --- |
| Local stack | Supabase CLI (Postgres + pgvector + Storage + Realtime) |
| Workflow execution | LangGraph inside Python workers or serverless functions |
| Artifact storage | Supabase buckets (`model-artifacts`, `feature-snapshots`) |
| Observability | Supabase logs, pg_stat statements, OpenTelemetry exporters |

### 2. Data & Feature Fabric

1. **Ingestion & labeling** – Python jobs land raw market data, regulatory events, or fundamentals in Supabase tables. Use cases attach labels using RPC helpers.
2. **Feature generation** – Feature scripts (for example `features/generate_ts2vec_embeddings.py`) produce embeddings and persist them to the `signal_embeddings` table via the Supabase REST API.
3. **Versioned metadata** – Each embedding row stores metadata (`source`, `regime`, `window`) enabling LangGraph agents to reason over provenance and drift.
4. **Automation hooks** – SQL in `supabase/sql/signal_embedding_triggers.sql` defines triggers and RPCs that notify agents whenever embeddings change.

### 3. Agentic Control Plane

1. **Planner** – `agents/langgraph_chain.py` builds a `StateGraph` that evaluates intents and routes them to supported Supabase-aware tools (`propose_new_feature`, `run_backtest`, `prune_vectors`, `refresh_vector_store`).
2. **Tooling** – `agents/tools.py` encapsulates Supabase RPC calls, table inserts, and vector maintenance primitives.
3. **Memory & feedback** – Results from each tool call are written back into the agent state, enabling subsequent planner iterations or downstream agents.

### 4. Strategy Evaluation

- **Backtesting** – Agents call `run_backtest()` which triggers the Supabase RPC `run_strategy_backtest`. The RPC can orchestrate vectorbt, custom SQL simulations, or serverless jobs.
- **Metric tracking** – Backtest outputs feed Supabase tables (`backtest_runs`, `strategy_metrics`) and optionally push analytics to dashboards.
- **Decisioning** – Agents use retrieved metrics to decide whether to refresh embeddings, prune stale vectors, or propose new features.

### 5. Deployment

- **Realtime retraining** – Supabase triggers watch inserts into `signal_embeddings` and publish events that spawn retraining jobs or call LangGraph subgraphs.
- **Artifact delivery** – Model checkpoints are stored in Supabase buckets. Deployment targets (Edge Functions, Kubernetes jobs, on-prem services) retrieve the latest artifact using signed URLs.
- **Feedback ingestion** – Live trading performance is captured in Supabase, closing the loop for the GPT agents.

## Use Case Integration Pattern

1. Implement a subclass of `StrategyUseCase` under `use_cases/<name>/pipeline.py` that builds the payload sent to the LangGraph agent.
2. Store custom preprocessing, labeling, or data fetching logic alongside the pipeline file.
3. Register embeddings in Supabase using `features/` helpers to make them discoverable by the agents.
4. Document the workflow with a Markdown file inside the same folder for humans.

## Extending the Framework

- Add RPCs in Supabase to support new agent tools (for example, `score_signal_cluster`).
- Introduce background workers that subscribe to Supabase realtime channels and invoke `build_langgraph_chain()` for asynchronous processing.
- Expand the Docusaurus docs to include each strategy and its metrics, keeping architecture references in-sync with code.
