---
id: use-cases-overview
title: Use Case Catalogue
description: Example scenarios that plug into the Agentic Quantitative Framework.
---

## Overview

Each use case combines Supabase data tables, LangGraph tooling, and Prefect flows to automate a specific research or trading workflow. Use this catalogue to explore existing implementations and discover how to contribute new ones.

## Available Use Cases

- [Insider Trading Loop](../../use_cases/insider_trading/Agentic%20Quant%20Loop.md) – Demonstrates how regulatory filings trigger feature generation, vector refreshes, and backtests through the shared infrastructure.

## Adding a New Use Case

1. Create a new directory under `use_cases/<your_use_case>/` with documentation and data-loading scripts.
2. Define ingestion pipelines that land data in Supabase tables; register any RPC helpers inside `supabase/sql/` or migrations.
3. Implement feature generation or embedding scripts under `features/` and register them via the LangGraph `propose_new_feature` tool.
4. Deploy Prefect flows for orchestration (embedding refresh, pruning, backtests) and document how to run them in this catalogue.

Link back to this README from your use case to ensure Docusaurus navigation stays consistent.
