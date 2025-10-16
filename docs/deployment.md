---
id: deployment
title: Deployment Playbook
description: Deploying Supabase-driven agent pipelines across environments.
---

## Environments

- **Local** – Supabase CLI (`supabase start`) plus the `.devcontainer` ensures Python 3.11, Node.js 18, Supabase CLI, and LangGraph dependencies.
- **Staging** – Hosted Supabase project mirroring local schema. Edge Functions invoke the same Python agents using container images built from this repository.
- **Production** – Supabase managed Postgres with observability enabled; workers run on Kubernetes or serverless platforms and subscribe to Supabase realtime events.

## Deployment Steps

1. **Migrate** – Use `supabase db push` to apply schema changes, triggers, and RPC updates.
2. **Build agents** – Package the Python runtime (Poetry or pip) and ensure environment variables (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`) are provided.
3. **Configure triggers** – Enable functions that react to `signal_embeddings` inserts to schedule retraining or vector refreshes.
4. **Ship artifacts** – Upload trained models to Supabase storage buckets and update metadata rows so agents can retrieve the latest version.
5. **Monitor** – Stream Supabase logs, track RPC latencies, and export agent decisions for auditability.

## Zero-Downtime Tips

- Use feature flags stored in Supabase tables to gate new strategies before general rollout.
- Maintain blue/green buckets for model artifacts and flip references atomically in the database.
- Schedule regular vector pruning with `prune_vectors` to keep pgvector indexes fast.

## Security

- Store service-role keys securely (GitHub Actions secrets, Vault) and expose read-only anon keys to UI clients only.
- Enable Row Level Security (RLS) policies and restrict RPC execution to trusted roles.
- Log all agent tool calls for compliance and incident response.
