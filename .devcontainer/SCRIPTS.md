# Scripts — One place to find them

All devcontainer scripts live under `.devcontainer/scripts/`. Additional optional CLI installers live in `scripts/` at the repo root.

## Devcontainer scripts

| Script | Purpose |
|---|---|
| `post-create.sh` | One‑time container setup. Enables Corepack/PNPM, runs `pnpm install` if `package.json` exists, installs Supabase CLI, Codex CLI, and Claude Code CLI. |
| `post-start.sh` | On container start: ensure Supabase is running, pull the Prefect Docker image that matches `prefect.yaml`, run Prefect server + docker work pool/worker containers, sync `.env.local` via `sync-supabase-env.mjs`. |
| `install-supabase-cli.sh` | Robust installer for Supabase CLI (latest or `SUPABASE_VERSION`). |
| `install-prefect-cli.sh` | Installs Prefect CLI via `pipx` (latest or `PREFECT_VERSION`) and injects the `prefect-docker` plugin so Docker workers have a base job template. |
| `install-codex-cli.sh` | Install OpenAI **Codex** CLI globally via **pnpm**. |
| `install-claude-code-cli.sh` | Install Anthropic **Claude Code** CLI globally via **pnpm**. |
| `sync-supabase-env.mjs` | Parses `supabase status` output and writes `.env.local` (prefers Publishable/Secret, backfills Anon/Service Role). |

### Usage snippets

```bash
# Refresh env after starting Supabase
.devcontainer/scripts/sync-supabase-env.mjs --out .env.local

# Reinstall Supabase CLI (specific version)
SUPABASE_VERSION=v2.8.6 .devcontainer/scripts/install-supabase-cli.sh
```

## Optional CLI installers (manual)

These are provided to keep the base image lean. Run them only if you need the tool.

| Script | Installs | Method |
|---|---|---|
| `scripts/install-aider-cli.sh` | Aider | `pipx install aider-chat` |
| `scripts/install-gemini-cli.sh` | Google Gemini CLI | `pnpm add -g @google/gemini-cli` |
| `scripts/install-goose-cli.sh` | Block Goose CLI | Vendor curl installer |
| `scripts/install-plandex-cli.sh` | Plandex CLI | Vendor curl installer |

> All installers use strict bash mode and verify the binary lands on `PATH`.
