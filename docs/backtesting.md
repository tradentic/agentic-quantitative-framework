---
id: backtesting
title: Backtesting & Evaluation
description: How Prefect flows, Supabase storage, and LangGraph agents coordinate strategy evaluation.
---

## Backtest Lifecycle

1. **Payload construction** – Use cases assemble a payload describing the asset universe, hyperparameters, and evaluation window.
2. **Agent invocation** – `run_backtest()` is called via the LangGraph planner or Prefect `scheduled-backtest-runner` flow. The tool
   executes `backtest/engine.py` locally and computes Sharpe, drawdown, and annualized return metrics.
3. **Artifact persistence** – Summaries are uploaded to Supabase Storage (`model-artifacts/backtests/<strategy>/<timestamp>/...`).
   Each run inserts a row into the `backtest_results` table via `framework.supabase_client.insert_backtest_result`, storing
   `config`, `metrics`, `artifacts`, and the strategy identifier used by downstream dashboards.
4. **Supabase visibility** – Requests originate from the `backtest_requests` table or realtime triggers. Prefect updates the table
   when jobs finish so dashboards can reflect the latest status and completed timestamps.

## Designing Backtests

- Keep raw market data in Supabase tables so runs can align vector similarity searches with relational filters.
- Version configs and feature bundles in Supabase `feature_registry` to tie proposals directly to evaluation runs.
- Store configuration metadata (hyperparameters, feature sets) alongside each run for reproducibility and auditability.

## Automating Evaluations

The Prefect deployment `scheduled-backtest-runner` polls `backtest_requests` for new work. Common triggers include:

- **Rolling evaluation** – Nightly replays of the last N days to monitor drift.
- **Trigger-based runs** – Launch a backtest when new embeddings arrive (`rpc_refresh_embeddings`) or when live metrics degrade.
- **Comparative studies** – Running multiple parameter grids and storing results under a shared experiment ID in Supabase.

## Reading Results

The backtest tool returns a structured dictionary with metric summaries and Supabase storage paths. Agents, notebooks, or Prefect
flows can follow up by querying `backtest_results` for the stored `config` metadata or by downloading artifacts from Storage to
re-plot curves. The canonical architecture remains documented in
[architecture/quant_ai_strategy_design.md](architecture/quant_ai_strategy_design.md).
