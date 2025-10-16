---
id: architecture
title: Reference Architecture
---

# Architecture

The framework is organised into layered modules:

- **Agents (`agents/`)** — LangGraph planners plus shared tool functions.
- **Feature factory (`features/`)** — declarative pipelines that transform raw
  market data into embeddings and factor exposures.
- **Backtests (`backtests/`)** — reusable evaluation jobs with deterministic
  outputs for agent review.
- **Vector memory (`vector_db/`)** — pgvector schemas, maintenance utilities,
  and drift monitoring routines.
- **Use cases (`use_cases/`)** — domain-specific manifests that bind data,
  labelling, and deployment policies together.

Docusaurus documentation lives in `docs/` while infrastructure helpers (CLI
setup, env sync, automation) reside in `scripts/infra/`.
