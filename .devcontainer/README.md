# Devcontainer Overview

A reproducible development environment tailored for the **Agentic Quantitative
Framework**.

## Toolchain

* **Base image**: Ubuntu 24.04 with Docker-in-Docker for the Supabase stack
* **Python**: 3.11 with Poetry pre-installed
* **Node.js**: 18.x for Docusaurus docs and UI tooling
* **Supabase CLI**: available globally for local-first database workflows

## Lifecycle hooks

* `postCreateCommand` → runs `.devcontainer/scripts/post-create.sh`
  * Installs Python dependencies with Poetry when `pyproject.toml` exists
  * Installs docs dependencies via `npm install` inside `docs/`
* `postStartCommand` → runs `.devcontainer/scripts/post-start.sh`
  * Ensures the Supabase stack is running locally
  * Calls `scripts/infra/sync-supabase-env.mjs` to refresh `.env.local`

## Ports

Port forwarding is configured for:

* `3000` — Docusaurus dev server
* `54321` — Supabase API Gateway
* `54322` — Supabase Postgres

## Quick verification

```bash
poetry --version
npm --version
supabase --version
```

These commands should succeed inside the container. If they do not, rebuild the
container and re-run `post-create.sh`.
