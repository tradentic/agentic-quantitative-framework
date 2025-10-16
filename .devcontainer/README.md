# Devcontainer Overview

A portable Codespaces/devcontainer that readies a **Next.js + Supabase** environment for scaffolding and local dev.

## What this sets up

* **Base image**: Ubuntu 24.04 with Docker‑in‑Docker
* **Tooling**: Node **24** (Corepack/PNPM enabled), Supabase CLI, optional AI CLIs (see `scripts/`)
* **Ports**: 3000 (Next), 4200 (Prefect UI/API), 3920/4002/4390 (Prefect background services), 54321/54322/54323/54324/54327 (Supabase stack)

## Lifecycle hooks

**Exactly what runs and why** — restored in full detail:

* `updateContentCommand`: noop (the repo may not have a `package.json` yet, so we don’t install deps prematurely)
* `postCreateCommand`: runs `.devcontainer/scripts/post-create.sh`

  * Enables corepack/pnpm
  * Installs deps **only if** `package.json` exists
  * Installs **Supabase CLI**
  * Installs **OpenAI Codex CLI** via **pnpm global** (no npm/brew)
  * *(Optional, if enabled in the script)* Installs **Anthropic Claude Code CLI** via **pnpm global**

* `postStartCommand`: runs `.devcontainer/scripts/post-start.sh`

  * Starts Supabase (`supabase start`) if not already running
  * Runs `.devcontainer/scripts/sync-supabase-env.mjs` to generate **`.env.local`** from `supabase status`
  * Prefers Supabase **Publishable/Secret** keys; falls back to **Anon/Service Role**; **backfills both ways** so either style works
  * Boots Prefect (`prefect server start --background --host 0.0.0.0 --port 4200`) and pins `PREFECT_API_URL` to the local server once healthy

> For script internals and flags, see **[SCRIPTS.md](./SCRIPTS.md)**.

## Extensions

Default VS Code extensions are minimal and **security‑aware** (ESLint, Axe Linter, Markdownlint, plus workflow helpers). Coding‑agent extensions are **suggested**, not installed. See **[EXTENSIONS.md](./EXTENSIONS.md)** for policy and secret‑leak notes.

## Environment sync (summary)

On start or on demand you can run:

```bash
.devcontainer/scripts/sync-supabase-env.mjs --out .env.local
```

This parses `supabase status` and writes the modern keys:

* `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
* server‑only `SUPABASE_SECRET_KEY`

It also maps/backs‑fills legacy names:

* `NEXT_PUBLIC_SUPABASE_ANON_KEY` ↔ publishable, and `SUPABASE_SERVICE_ROLE_KEY` ↔ secret

## Quick checks

```bash
supabase --version || echo 'supabase missing'
node -v && pnpm -v
```

## Troubleshooting

* **CLI not on PATH** after install: add `$(pnpm bin -g)` or `$HOME/.local/bin` to `PATH`.
* **No `.env.local`**: ensure Supabase is running, then run the sync script with `--out`.

## Why commit this?

Keeping a stable, documented environment checked in makes your “latest CNA” scaffolds predictable while letting app code stay fresh.
