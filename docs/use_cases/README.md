---
id: use-cases-readme
title: Use Case Index
description: Entry points for portfolio-specific research loops and how to adapt them.
---

## Getting Started

Each quantitative workflow lives under `use_cases/`. Start with the insider trading prototype to understand how LangGraph agents,
Supabase tables, and Prefect flows coordinate across the stack.

- [Insider Trading Quant Loop](../../use_cases/insider_trading/Agentic%20Quant%20Loop.md)
- [`use_cases/` package overview](../../use_cases/README.md)

## Adding a New Use Case

1. Create a directory under `use_cases/<your_use_case>/` with feature extraction, labeling, and orchestration helpers.
2. Document the lifecycle using Markdown so it can be cross-linked from Docusaurus.
3. Register any Supabase tables, RPCs, or Prefect flows needed for the new workflow.
