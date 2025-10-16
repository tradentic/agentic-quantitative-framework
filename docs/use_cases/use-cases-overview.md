---
id: use-cases-overview
title: Use Cases Overview
sidebar_position: 1
---

The Agentic Quantitative Framework organizes applied strategies into modular use cases. Each use case bundles its own data
adapters, labeling logic, feature generators, and orchestration hooks so that strategies can evolve independently while
sharing the same LangGraph and Supabase infrastructure. This overview summarizes how to extend the repository with new
strategies and what currently ships out of the box.

## What lives in `use_cases/`

The Python package at `use_cases/` contains reusable abstractions for strategy-specific pipelines:

- `base.py` defines the `StrategyUseCase` base class that standardizes orchestration hooks.
- `insider_trading/` demonstrates how to wire labeling, feature extraction, and agent prompts around a specific dataset.
- `README.md` documents the registration process for adding additional strategies.

Each use case exports a `pipeline.py` module that agents call to assemble the context sent into LangGraph. Supporting
artifacts—feature configs, prompts, and evaluation routines—live beside the pipeline to keep dependencies localized.

## Adding a new use case

1. Create a new directory under `use_cases/<strategy_name>/` and implement a subclass of `StrategyUseCase` that prepares the
   data payload required by the LangGraph agents.
2. Capture domain-specific prompts in `prompts/` or alongside the new use case so that automated runs stay reproducible.
3. Register any recurring jobs in `flows/` or `prefect.yaml` so Prefect can orchestrate refreshes and evaluations.
4. Update documentation and sponsorship materials if the new strategy introduces external dependencies or licensing notes.

## When to document a use case

Authoring a new use case should always include a documentation update. Adding a brief README within the use case directory and
linking to it from this overview keeps downstream contributors informed about available strategies, required credentials, and
live automation hooks.
