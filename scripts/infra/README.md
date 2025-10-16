# Infrastructure Scripts

Shared automation used by the Agentic Quantitative Framework lives here. Keep
scripts idempotent so they can be executed from CI, devcontainers, or manual
runs without side effects.

Current utilities:

- `sync-supabase-env.mjs` — generates `.env` files from the local Supabase
  status output.
