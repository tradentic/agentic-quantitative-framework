# Agentic Quantitative Framework

Supabase-first reference implementation for LangGraph-powered quantitative research agents. The framework coordinates GPT planners, Prefect automation, and Supabase pgvector storage so strategies can self-evaluate, retrain, and publish signals continuously.

## Architecture Overview

- **Agentic planning loop** – `agents/langgraph_chain.py` orchestrates LangGraph tool calls that propose new features, trigger backtests, and manage vector pruning across use cases.
- **Supabase integration** – `agents/tools.py` and `framework/supabase_client.py` wrap RPCs, vector tables, and metadata helpers so agents can persist embeddings and retrieve historical context.
- **Feature + signal factory** – `features/` houses TS2Vec, DeepLOB, and symbolic regression scripts that materialize pgvector rows and register feature metadata.
- **Evaluation & orchestration** – Prefect flows in `flows/` schedule backtests, embedding refreshes, and nightly maintenance using the definitions in `prefect.yaml`.
- **Use-case isolation** – Strategies under `use_cases/<name>/` define event windows, labeling logic, and payload builders that plug into the shared agent loop.

## Repository Layout

| Path | Summary |
| --- | --- |
| `agents/` | LangGraph chain entry points, tool definitions, and compatibility shims for Supabase + Prefect execution. |
| `backtest/` | Portfolio and performance utilities for validating proposed signals, including sharpe/decay diagnostics consumed by agents. |
| `features/` | Feature generation notebooks and scripts that persist embeddings and metadata to Supabase. |
| `flows/` | Prefect 2.x flow definitions for recurring maintenance jobs such as vector pruning and retraining. |
| `framework/` | Core client helpers (Supabase, logging, config) shared across agents, flows, and features. |
| `supabase/` | Supabase configuration, migrations, and seed scripts for local development. |
| `use_cases/` | Modular strategy packages (e.g., `insider_trading/`) that define task-specific pipelines and documentation. |
| `docs/` | Docusaurus site containing architecture deep dives, ADRs, and operational runbooks. |
| `LOCAL_DEV_SETUP.md` | End-to-end local environment guide covering Supabase CLI, environment variables, and Prefect setup. |
| `tests/` | Unit and integration tests validating agent utilities and feature pipelines. |

## Documentation & References

- [Local development setup](LOCAL_DEV_SETUP.md) – Supabase CLI bootstrap, environment variables, and workflow automation hints.
- [Quant AI strategy design](docs/architecture/quant_ai_strategy_design.md) – Explains the closed-loop agent workflow, Supabase schemas, and orchestration patterns.
- [Use case guides](use_cases/) – Each use case folder contains domain-specific notes such as the insider trading loop (`use_cases/insider_trading/Agentic Quant Loop.md`).
- [Change history](CHANGELOG.md) – Highlights notable updates across flows, features, and documentation.

## Getting Started

1. Bootstrap the Python environment:
   ```bash
   make dev  # creates .venv and installs project dependencies
   ```
2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Update Supabase keys and LangGraph credentials as described in [`LOCAL_DEV_SETUP.md`](LOCAL_DEV_SETUP.md).
3. Launch Supabase locally:
   ```bash
   supabase start
   ```
4. Run migrations and seed data (optional but recommended):
   ```bash
   supabase db reset
   ```
5. Start Prefect services and register flows:
   ```bash
   prefect server start &
   prefect deployment apply prefect.yaml
   ```
6. Validate the agent graph wiring:
   ```bash
   python -c "from agents import build_langgraph_chain; build_langgraph_chain()"
   ```

Explore the [docs site](docs/) for architecture diagrams, operational runbooks, and troubleshooting tips once the local environment is running.
