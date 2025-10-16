# Local Development Setup

The Agentic Quantitative Framework is designed for a Supabase-first, local workflow. The sections below walk through the
recommended commands for bootstrapping the database, Prefect orchestration, and Python tooling.

## 1. Prerequisites

- Docker (required by the Supabase CLI)
- [Supabase CLI](https://supabase.com/docs/guides/cli) `>= 1.150`
- Python 3.11+
- Node.js 24 LTS (for docs and optional frontends)

Clone the repository and create a virtual environment with the provided `Makefile` target:

```bash
git clone https://github.com/YOUR_USERNAME/agentic-quantitative-framework.git
cd agentic-quantitative-framework
make dev
```

> The `make dev` target provisions `.venv` and installs the editable package along with lint/type-check tooling.

## 2. Supabase Local Stack

Start the full Supabase stack (Postgres + auth + storage) locally:

```bash
supabase start
```

### Reset the Database

Apply all migrations and reseed the database in one step. This command is safe to run whenever you need a clean slate:

```bash
supabase db reset --local
```

### Push New Migrations

When you add new migrations and want to apply them without a full reset, target the local stack explicitly:

```bash
supabase db push --local --dry-run
supabase db push --local
```

Later, if you link a remote Supabase project (`supabase link`), reuse `supabase db push --linked` to mirror the same schema.

Supabase automatically executes `supabase/seed.sql` during `db reset`, populating feature registry, signal embeddings, and a
sample backtest result for smoke-testing LangGraph tools and Prefect flows.

## 3. Prefect Orchestration

Install Prefect (if it is not already present in your virtual environment) and verify the version:

```bash
pip install -U prefect
prefect version
```

Launch the local Prefect server (UI + API). The server automatically applies its own migrations on startup:

```bash
prefect server start --host 127.0.0.1 --port 4200
```

With the server running, you can execute the local flows directly from this repository. For example, to recompute embeddings for
pending jobs pulled from Supabase:

```bash
python flows/embedding_flow.py
```

Repeat the same pattern for `flows/backtest_flow.py` and `flows/prune_flow.py` when testing orchestration logic.

## 4. Environment Variables

Use `supabase status` after the stack boots to capture generated connection strings. The `.devcontainer/scripts`
folder contains utilities for syncing those values into `.env.local` files if needed for front-end apps or additional
services.

## 5. Additional Tooling

The `Makefile` exposes helpers for the most common workflows:

```bash
make supabase   # supabase start
make resetdb    # supabase db reset --local
make pushdb     # supabase db push --local
make prefect    # prefect server start --host 127.0.0.1 --port 4200
make lint       # ruff check + mypy
```

Refer to `docs/architecture/quant_ai_strategy_design.md` for the end-to-end system blueprint that these local commands
support.
