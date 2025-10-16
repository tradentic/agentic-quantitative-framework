This project is fully compatible with local-first development using the `supabase` CLI, LangGraph, and Prefect.

## Prerequisites

- Docker installed
- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Python 3.11+
- Node.js 18+ (for the Docusaurus docs dev server)
- `pip` or `uv` for Python dependency management

## Bootstrap the Repository

```bash
git clone https://github.com/YOUR_USERNAME/agentic-quantitative-framework.git
cd agentic-quantitative-framework

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install JS dependencies for docs if needed
pnpm install
```

## Supabase Local Stack

```bash
# Start the Supabase containers (Postgres, pgvector, storage, realtime)
supabase start

# Apply RPC helpers/triggers after the stack is running
supabase db execute --file supabase/sql/signal_embedding_triggers.sql
```

### Resetting Local State

- `supabase db reset --local` – Recreates the local Postgres container, reapplies every SQL migration, and runs `supabase/seed.sql` automatically. Use this to guarantee a clean slate when iterating on schema changes or testing seeds.
- To re-run only the seeds, run `supabase db reset --local`. The CLI always loads `supabase/seed.sql` after migrations are replayed.

### Pushing Schema Changes

- `supabase db push --local` – Validates the migration bundle against your local containers. Useful before linking a remote project.
- `supabase db push --linked` – Pushes the current migrations to the linked Supabase project. Append `--dry-run` to inspect SQL without executing.
- For self-hosted targets provide `--db-url <postgres-connection-string>` instead of `--linked`.

### Seeded Data

`supabase/seed.sql` inserts:

- A baseline TS2Vec feature registry row
- Two example `signal_embeddings` rows with 128-dimension vectors
- A sample `backtest_results` record that references Supabase Storage artifact paths

After running `supabase start` or `supabase db reset --local`, verify the data with `supabase db remote commit --db-url postgresql://postgres:postgres@localhost:54322/postgres --schema public --schema-only=false` if desired (or use psql directly).

## Prefect Local Orchestration

```bash
pip install prefect
prefect server start  # UI at http://127.0.0.1:4200

# If you run flows from another shell, target the local API
export PREFECT_API_URL=http://127.0.0.1:4200/api

# Execute a flow locally
prefect run python -m flows.embedding_flow
```

## LangGraph Agent Smoke Test

```python
from agents.langgraph_chain import build_langgraph_chain

graph = build_langgraph_chain()
graph.invoke({"task_context": {"request": "Run a sample backtest", "agent_id": "demo-agent"}}, config={"thread_id": "demo-thread"})
```

The LangGraph checkpointer stores thread state under `.cache/langgraph_state.sqlite`, while Supabase persists long-term memory in the `agent_state` table.
