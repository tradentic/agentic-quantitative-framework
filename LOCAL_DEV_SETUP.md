# Local Development

Follow these steps to run the Agentic Quantitative Framework locally with the
Supabase CLI.

## Prerequisites

- Docker
- Supabase CLI (`brew install supabase/tap/supabase` or download from releases)
- Python 3.11+
- Poetry (`pipx install poetry` or use the devcontainer)
- Node.js 18+ (for the documentation site)

## Initial Setup

```bash
# Clone the repository
git clone https://github.com/<your-org>/agentic-quantitative-framework.git
cd agentic-quantitative-framework

# Install Python dependencies
poetry install --no-root

# Start Supabase locally
supabase start

# Prepare pgvector tables
psql postgresql://postgres:postgres@localhost:54322/postgres \
  -f supabase/vector_db/setup_pgvector.sql

# Copy environment variables
cp .env.example .env
```

Populate `.env` with your Supabase keys plus any model API keys the agents
require.

## Running Agents

```bash
poetry run python -m agents.langgraph_chain
```

This executes the LangGraph planner end-to-end and prints the resulting state.

## Documentation Site

```bash
cd docs
npm install
npm run start
```

The docs server listens on http://localhost:3000 and documents the architecture
and workflows.
