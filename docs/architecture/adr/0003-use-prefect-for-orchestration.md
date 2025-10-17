---
id: adr-0003-use-prefect-for-orchestration
title: ADR 0003 – Use Prefect for Orchestration
sidebar_position: 3
---

## Status

Accepted – Prefect remains the default orchestrator for local development and scheduled automation.

## Context

The framework requires a workflow engine that is easy to run locally, integrates with Python-native code, and scales to more
formal deployments. We compared Prefect, Airflow, and Dagster with an emphasis on developer efficiency and LangGraph
compatibility:

- **Airflow** – Battle-tested at scale but heavy for local iteration, with YAML-forward DAG definitions and steeper infra
  requirements per developer.
- **Dagster** – Strong asset semantics yet adds ceremony, type boilerplate, and an additional control plane to maintain.
- **Prefect** – Python-first API, lightweight local server and UI, fits nicely with our existing `prefect.yaml`, and delivers
  clear observability for LangGraph-triggered jobs.

## Decision

Adopt **Prefect 3.x** for local flows that cover embedding refresh, backtest execution, and scheduled pruning. Keep the flow
surface thin so another orchestrator can be swapped in later if requirements change. Prefect's declarative deployments and
hosted UI give agents immediate observability without forcing a heavy scheduler onto local workstations.

## Consequences

- Lightweight scheduling, retries, and a local UI help teams observe flow runs without new infrastructure.
- Supabase-triggered jobs (embedding refresh, pruning) stay Pythonic while still benefiting from structured orchestration, and
  LangGraph agents can hand off slower cadence work to Prefect flows.
- Developers can run `prefect server start` locally and apply deployments via `prefect deployment apply prefect.yaml` to mirror
  production-style schedules.
- Future migrations to Prefect Cloud—or an alternative platform—remain low-risk because orchestration boundaries are
  concentrated in the `flows/` package.
