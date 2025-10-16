---
id: deployment
title: Deployment Playbook
description: Deploying Supabase-first agents, Prefect flows, and documentation.
---

## Environments

- **Local** – Start Supabase with `supabase start`, apply migrations via `supabase db push --local`, and run Prefect locally
  (`prefect server start --host 127.0.0.1 --port 4200`). The `.devcontainer` captures the Python, Node.js 24 LTS, and Supabase CLI
  versions used by CI.
- **Staging** – Mirror the local schema in a managed Supabase project. Prefect agents run near the database and authenticate with
  service-role keys for backtest writes and vector refresh jobs.
- **Production** – Promote the same migrations with `supabase db push --linked` after linking the remote project. LangGraph agents
  use Supabase RPCs, storage buckets, and pgvector indexes for long-term memory.

## Local Deployment Steps

1. **Start Supabase services**
   ```bash
   supabase start
   ```
2. **Reset or migrate the database**
   ```bash
   supabase db reset --local          # applies migrations + supabase/seed.sql
   supabase db push --local --dry-run # validate pending migrations
   supabase db push --local           # apply without a full reset
   ```
3. **Launch Prefect for orchestration**
   ```bash
   pip install -U prefect
   prefect server start
   ```
   Prefect applies its own schema migrations on startup. If you want to point CLI commands at the local API explicitly, export
   `PREFECT_API_URL=http://127.0.0.1:4200/api` in your shell. Run flows directly for smoke tests with
   `prefect run python -m flows.embedding_flow` (and the analogous `flows.backtest_flow` / `flows.prune_flow`).
4. **Ship artifacts** – Upload new feature scripts or model outputs to Supabase storage (see `agents/tools.py` helpers) and update
   registry tables so agents discover them automatically.
5. **Monitor** – Track `backtest_results` and `signal_embeddings` tables in Supabase Studio, and use the Prefect UI to observe
   scheduled flows (`scheduled-backtest-runner`, `supabase-embedding-refresh`, `scheduled-vector-prune`).

## Prefect Adoption

See [architecture/quant_ai_strategy_design.md](architecture/quant_ai_strategy_design.md) for the canonical blueprint describing
how LangGraph planners, Supabase storage, and Prefect orchestration interact. Prefect was selected for:

- Python-native, local-first development with automatic retries and logging.
- Seamless promotion from a local server to Prefect Cloud without rewriting flows.
- Tight integration with Supabase RPC triggers and vector maintenance jobs.

## Zero-Downtime Tips

- Gate new strategies with feature flags stored in Supabase tables before enabling them in production flows.
- Keep dual storage prefixes for artifacts (`model-artifacts/backtests/...`) and update registry rows atomically when promoting a
  new model.
- Schedule pruning flows so the pgvector IVFFLAT index stays performant while archived data lands in `signal_embeddings_archive`.

## Security

- Store Supabase service-role keys in secure secrets managers (e.g., GitHub Actions secrets, Vault).
- Enable Row Level Security (RLS) on Supabase tables and restrict RPC execution to trusted roles.
- Log every LangGraph tool call and Prefect flow run for auditability.
