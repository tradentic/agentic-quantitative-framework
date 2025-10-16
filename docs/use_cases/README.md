---
id: use-cases-readme
title: Use Case Catalog
description: Overview of strategy-specific pipelines and reference notebooks.
---

## Available Use Cases

- [Insider trading quant loop](@site/use_cases/insider_trading/Agentic%20Quant%20Loop.md) – Walks through labeling, feature generation, and evaluation steps tailored to corporate insider trading disclosures.

## Conventions

1. Each strategy lives under `use_cases/<name>/` with a `pipeline.py` entry point that builds LangGraph payloads.
2. Documentation for the strategy should ship alongside the implementation and be linked from this README.
3. Sample assets (feature configs, evaluation notebooks) belong in Supabase Storage buckets referenced by the metadata recorded in `feature_registry`.
