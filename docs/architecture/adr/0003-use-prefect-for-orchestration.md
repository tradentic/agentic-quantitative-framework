---
id: adr-0003-use-prefect-for-orchestration
title: ADR 0003 – Use Prefect for Orchestration
sidebar_position: 3
---

## Context

We evaluated Airflow, Dagster, and other orchestrators. Developer experience, local-first execution, and low ceremony were the
primary decision filters so individual researchers can iterate quickly alongside LangGraph agents.

## Decision

Adopt **Prefect** for local flows that cover embedding refresh, backtest execution, and scheduled pruning. Keep the flow surface
thin so another orchestrator can be swapped in later if the requirements change.

## Consequences

- Lightweight scheduling, retries, and a local UI help teams observe flow runs without new infrastructure.
- Supabase-triggered jobs (embedding refresh, pruning) stay Pythonic while still benefiting from structured orchestration.
- Future migrations to Prefect Cloud—or an alternative platform—remain low-risk because orchestration boundaries are
  concentrated in the `flows/` package.
