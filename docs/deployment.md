---
id: deployment
title: Deployment & Operations
---

# Deployment & Operations

1. **Bootstrap Supabase**
   - Install Docker and the Supabase CLI
   - Run `supabase start` and execute `supabase/vector_db/setup_pgvector.sql`
2. **Install dependencies**
   - Use the devcontainer or run `poetry install` locally
   - Install docs tooling with `npm install` in `docs/`
3. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - Populate Supabase credentials and model API keys
4. **Run agents and pipelines**
   - Execute LangGraph planners via `python -m agents.langgraph_chain`
   - Trigger backtests with the scripts in `backtests/`

For production deployments, mirror the Supabase configuration and ensure vector
maintenance jobs are scheduled via cron or Supabase Edge Functions.
