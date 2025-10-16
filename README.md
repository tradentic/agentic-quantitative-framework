# Agentic Quantitative Framework

A LangGraph-native research stack for discovering quantitative trading signals.
The framework blends agentic planners, feature factories, deterministic
backtests, and Supabase-backed vector memory into a cohesive workflow.

## Repository Structure

- `agents/` — LangGraph planners plus tool functions (`propose_new_feature`,
  `run_backtest`, `prune_vectors`, `refresh_vector_store`).
- `features/` — Feature generation scripts (e.g., TS2Vec embeddings).
- `backtests/` — Scenario manifests, jobs, and reports for evaluating signals.
- `vector_db/` — pgvector helpers and monitoring utilities.
- `config/` — Shared configuration for models, features, and schedules.
- `use_cases/` — Domain-specific playbooks such as insider trading loops.
- `docs/` — Docusaurus site for architecture, agents, and deployment guides.
- `scripts/infra/` — Infrastructure automation (Supabase env sync, etc.).
- `supabase/` — Local Supabase project configuration and migrations.

## Quickstart

```bash
# Clone and enter the repository
git clone https://github.com/<your-org>/agentic-quantitative-framework.git
cd agentic-quantitative-framework

# Bootstrap Python environment
poetry install --no-root

# Start Supabase locally
supabase start
psql postgresql://postgres:postgres@localhost:54322/postgres \
  -f supabase/vector_db/setup_pgvector.sql

# Run the LangGraph planner
poetry run python -m agents.langgraph_chain
```

See [`LOCAL_DEV_SETUP.md`](./LOCAL_DEV_SETUP.md) for the full development
environment guide, including devcontainer usage.

## Documentation

The Docusaurus site in `docs/` ships with placeholder pages:

- Overview of the Agentic Quantitative Framework
- Agent orchestration and tooling
- Architecture reference
- Deployment checklist

Launch the docs locally with:

```bash
cd docs
npm install
npm run start
```

## License

This project is open-sourced under the [MIT License](./LICENSE).
