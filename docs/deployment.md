---
id: deployment
title: Deployment Playbook
description: Deploying Supabase-first agents, Prefect flows, and documentation.
---

## Environments

- **Local** – Supabase CLI (`supabase start`), Prefect server (`prefect server start`), and the `.devcontainer` ensure Python
  3.11, Node.js 24, Supabase CLI, and LangGraph dependencies.
- **Staging** – Hosted Supabase project mirroring local schema. Prefect Orion agents run in the same VPC and connect back to the
  Supabase Postgres instance via service-role keys.
- **Production** – Supabase managed Postgres with observability enabled; workers run on Kubernetes or serverless platforms and
  subscribe to Supabase realtime events and Prefect deployments.

## Deployment Steps

1. **Migrate** – Use `supabase db push` to apply schema changes, triggers, and RPC updates (including `rpc_refresh_embeddings`
   and `rpc_prune_vectors`).
2. **Build agents** – Package the Python runtime with `pyproject.toml` dependencies, ensuring environment variables (`SUPABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`) are provided.
3. **Configure Prefect** – Start Prefect locally (`prefect server start`), then register deployments via `prefect deployment apply
   prefect.yaml`. Prefect flows publish logs for embedding refreshes, scheduled backtests, and pruning jobs.
4. **Ship artifacts** – Upload trained models to Supabase storage buckets and update metadata rows so agents and flows retrieve
   the latest versions.
5. **Monitor** – Stream Supabase logs, track RPC latencies, inspect Prefect UI for retries, and export agent decisions for audit.

## Prefect Adoption

See [ADR 0003](architecture/adr/0003-use-prefect-for-orchestration.md) for the decision to standardize on Prefect. Key benefits:

- Local-first developer experience with Python-native flows and automatic retries.
- Simple promotion path from local orchestration to Prefect Cloud without rewriting code.
- Unified logging and scheduling for LangGraph agents, Supabase RPCs, and embedding refresh jobs.

## Zero-Downtime Tips

- Use feature flags stored in Supabase tables to gate new strategies before general rollout.
- Maintain blue/green buckets for model artifacts and flip references atomically in the database.
- Schedule regular vector pruning with `prune_vectors` or the Prefect `nightly-prune-dev` deployment to keep pgvector indexes fast.

## Security

- Store service-role keys securely (GitHub Actions secrets, Vault) and expose read-only anon keys to UI clients only.
- Enable Row Level Security (RLS) policies and restrict RPC execution to trusted roles.
- Log all agent tool calls and Prefect flow runs for compliance and incident response.
