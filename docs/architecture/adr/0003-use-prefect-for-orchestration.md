---
id: adr-0003-use-prefect-for-orchestration
title: ADR 0003 – Use Prefect for Orchestration
sidebar_position: 3
---

## Status

Accepted – Prefect is the default orchestrator for local development and scheduled automation.

## Context

The framework requires a workflow engine that is easy to run locally, integrates with Python-native code, and scales to more
formal deployments. We compared Prefect, Airflow, and Dagster:

- **Airflow** – Battle-tested at scale but heavy for local iteration, with YAML-heavy DAGs and less friendly dynamic task authoring.
- **Dagster** – Strong data-asset semantics but adds a steeper learning curve and more infrastructure to manage per developer.
- **Prefect** – Python-first API, excellent local server and UI, and straightforward deployment configuration via `prefect.yaml`.

## Decision

Adopt Prefect 2.x as the orchestration layer for embedding refresh jobs, scheduled backtests, and vector pruning. Prefect's
declarative deployments and hosted UI give agents immediate observability without forcing a complex scheduler onto local
workstations. The LangGraph chain remains responsible for planning and tool execution, while Prefect handles cadence and retries.

## Consequences

- Developers run `prefect server start` locally and apply deployments via `prefect deployment apply prefect.yaml` to mirror prod
  schedules.
- Supabase realtime events can trigger Prefect flow runs, allowing pgvector updates and backtests to remain event-driven.
- Should scaling requirements change, Prefect Cloud can be adopted without re-authoring flows, but we can still swap schedulers
  later by keeping orchestration touchpoints isolated in the `flows/` package.
