# Backtest Pipelines

This directory contains reusable evaluation workflows for the Agentic Quantitative Framework.

- `scenarios/` holds definitions of market regimes and evaluation windows.
- `jobs/` stores orchestration manifests for scheduled backtests.
- `reports/` collects generated analytics that agents parse when scoring features.

Each backtest artifact should be reproducible via Poetry scripts or Supabase edge
functions so that LangGraph agents can trigger them deterministically.
