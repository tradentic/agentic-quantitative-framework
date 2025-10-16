# Local Development with Supabase & Prefect

This project is designed for a Supabase-first workflow. All schema, RPC helpers, and triggers live in
`supabase/migrations/` and are applied automatically by the Supabase CLI.

## Prerequisites

- Docker installed
- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Python 3.11+
- Node.js 18+ (for the Docusaurus docs site)

## Setup Steps

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/agentic-quantitative-framework.git
cd agentic-quantitative-framework

# Bootstrap Python environment (optional: use `make dev`)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# Start the local Supabase stack
supabase start

# Reset the local database: applies every migration then runs supabase/seed.sql
supabase db reset --local

# Optional: dry-run a migration push locally or against a linked project
supabase db push --local --dry-run
# supabase db push --linked --dry-run

# Launch Prefect's local server
pip install prefect
prefect server start
# (optional) export PREFECT_API_URL=http://127.0.0.1:4200/api

# Run Prefect flows ad-hoc
prefect run python -m flows.embedding_flow
prefect run python -m flows.backtest_flow
prefect run python -m flows.prune_flow

# Smoke test the LangGraph planner
python -c "from agents.langgraph_chain import run_planner; print(run_planner({'request': 'hello world'}))"
```

The `supabase db reset --local` command rebuilds the local Postgres instance, applies every
`supabase/migrations/*.sql` file in order, and finally loads sample data from `supabase/seed.sql` so
flows and agents have realistic starting points.
