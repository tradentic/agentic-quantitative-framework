---
id: backtesting
title: Backtesting & Evaluation
description: How Supabase RPCs and LangGraph agents coordinate strategy evaluation.
---

## Backtest Lifecycle

1. **Payload construction** – Use cases assemble a payload describing the asset universe, hyperparameters, and evaluation window.
2. **Agent invocation** – `run_backtest()` is called via the LangGraph chain, forwarding the payload to the Supabase RPC `run_strategy_backtest`.
3. **Computation** – The RPC launches a stored procedure, Edge Function, or external worker that executes vectorbt/NumPy-based simulations.
4. **Result storage** – Metrics are persisted to Supabase tables such as `backtest_runs` and `strategy_metrics`. Agents record the RPC response for immediate feedback.

## Designing Backtests

- Keep raw market data in Supabase to allow SQL-based slicing and labeling.
- Pre-compute embeddings using `features/` modules so backtests can combine relational filters with vector similarity search.
- Store configuration metadata (hyperparameters, feature sets) alongside each run for reproducibility.

## Automating Evaluations

Supabase cron jobs or GitHub Actions can call Edge Functions that publish events to the LangGraph planner. Typical automations include:

- **Rolling evaluation** – Weekly replays of the last N days to monitor drift.
- **Trigger-based runs** – Launching a backtest when new embeddings arrive or when live metrics deteriorate.
- **Comparative studies** – Running multiple parameter grids and storing results under a shared experiment ID.

## Reading Results

The RPC response contains the Supabase job identifier, enabling agents to poll for completion or fetch metrics via `client.table("backtest_runs").select().eq("job_id", ...)`.

Agents can summarize outcomes (Sharpe, drawdown, hit rate) and decide whether to refresh embeddings, prune vectors, or propose new features.
