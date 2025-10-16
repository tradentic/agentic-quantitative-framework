---
sidebar_position: 1
id: intro
slug: /
title: Welcome
description: Start here to understand the Agentic Quantitative Framework and its Supabase-first architecture.
---

# Agentic Quantitative Framework

This documentation hub explains how GPT-native agents, LangGraph workflows, and Supabase services collaborate to discover and maintain quantitative trading signals.

## What you'll find

- **Architecture overview** – Dive into the [Quant AI Strategy Design](architecture/quant_ai_strategy_design.md) to understand the layered system.
- **Agent orchestration** – Learn how the LangGraph planner uses Supabase-backed tools in [Agent Orchestration](agents.md).
- **Backtesting guidance** – Follow the [Backtesting & Evaluation](backtesting.md) playbook to automate strategy reviews.
- **Deployment practices** – Review the [Deployment Playbook](deployment.md) for promoting agents across environments.

## Quick start

1. Clone the repo and open it in the provided devcontainer.
2. Run `supabase start` to provision the local stack.
3. Execute `python -c "from agents import run_planner; print(run_planner({'request': 'ping'}))"` to validate the runtime.
4. Explore the `use_cases/` directory to see how strategies plug into the framework.

Refer back to these docs whenever you add new tools, Supabase RPCs, or strategy modules.

