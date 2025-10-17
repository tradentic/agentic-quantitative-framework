# Local Development: Supabase + Prefect

This guide walks through running the SEC Form 4 insider workflow end-to-end with local Supabase and Prefect services. Pair this with the Quickstart in the repository `README` when you want the full context, troubleshooting tips, and platform-specific notes.

## Supabase Local Setup

1. **Install the Supabase CLI.**
   - macOS: `brew install supabase/tap/supabase`
   - Linux: `curl -fsSL https://supabase.io/install.sh | sh`
   - Node-based alternative: `npm install -g supabase`
   Refer to the [Supabase CLI docs](https://supabase.com/docs/guides/cli/getting-started) for the latest installation guidance.
2. **Start the local Supabase stack and seed fixtures.**
   ```bash
   supabase start
   supabase db reset --local
   ```
   `supabase start` launches Postgres, Auth, and the Studio dashboard. `supabase db reset --local` reapplies the migrations under [`supabase/migrations/`](../../supabase/migrations) and loads the seed content in [`supabase/seed.sql`](../../supabase/seed.sql) plus JSON fixtures inside [`supabase/seed/`](../../supabase/seed/).
3. **Inspect the database (optional).**
   - Run `supabase status` to print connection details (default Postgres URL is `postgresql://postgres:postgres@127.0.0.1:54322/postgres`).
   - Connect pgAdmin, TablePlus, or psql using that URL to browse tables like `form4_filings`, `signal_embeddings`, and `signal_fingerprints`.
   - Supabase Studio is available at [http://127.0.0.1:54323](http://127.0.0.1:54323) with the credentials shown in the CLI output.

## Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env.local
   ```
2. Populate Supabase credentials so both the CLI utilities and the pipeline can talk to your local stack:
   ```bash
   SUPABASE_URL=http://127.0.0.1:54321
   SUPABASE_ANON_KEY=<anon-key-from-supabase-status>
   SUPABASE_SERVICE_ROLE_KEY=<service-role-key-from-supabase-status>
   ```
   - The CLI prints fresh keys after `supabase start`; fetch them again with `supabase status --json | jq` if you misplace them.
   - Add any additional secrets (e.g., vendor APIs) required by modules you plan to run outside of `--mock` mode.
3. Export the file for shells or devcontainers:
   ```bash
   set -a && source .env.local && set +a
   ```
   In GitHub Codespaces, add the same variables to `.devcontainer/devcontainer.json` or the Codespaces secrets UI so they are injected on boot.

## Python & Prefect Setup

1. **Create an isolated environment and install dependencies.**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   pip install -U prefect
   ```
   The editable install provides the pipeline entry points (`use_cases.insider_trading.pipeline`) and Prefect flow packages.
2. **Start Prefect orchestration services.**
   ```bash
   prefect server start --host 127.0.0.1 --port 4200
   ```
   - When running in Codespaces or Docker, use `--host 0.0.0.0` so the Prefect UI is accessible over the forwarded port.
   - Visit [http://127.0.0.1:4200](http://127.0.0.1:4200) to confirm the API and UI are reachable.
3. **Register the deployments defined in [`prefect.yaml`](../../prefect.yaml).**
   ```bash
   prefect deployment apply prefect.yaml
   ```
4. **Run a local agent or work pool worker.** Prefect deployments target the `my-docker-pool` work pool by default, so start an agent that listens on that queue:
   ```bash
   prefect agent start -q my-docker-pool
   ```
   If you prefer Prefect workers, create the pool first (`prefect work-pool create my-docker-pool --type docker`) and launch `prefect worker start --pool my-docker-pool` inside your container runtime.

## Run Modes & Pipeline Flags

The insider pipeline loads its execution graph from [`use_cases/insider_trading/config.yaml`](../../use_cases/insider_trading/config.yaml). Each mode maps to a sequence of modules (ingest, features, embeddings, fingerprints, scans, backtest).

- **`--mode train`** runs the full training-oriented path, including historical feature refreshes.
- **`--mode score`** runs the default scoring chain against a specific filing date.
- **`--mode refresh`** executes incremental maintenance modules.

Examples:

```bash
python -m use_cases.insider_trading.pipeline --mode train --date-from 2024-01-01 --date-to 2024-01-31 --mock
python -m use_cases.insider_trading.pipeline --mode score --date 2024-12-31 --symbol ACME --mock
python -m use_cases.insider_trading.pipeline --mode refresh --symbol ACME --no-fail-fast
```

Additional flags:

- `--mock` bypasses vendor integrations and relies solely on the Supabase seed data—perfect for local smoke tests.
- Omit `--mock` once you have production credentials in `.env.local` and want to hit external data sources.
- Use `--config /path/to/custom.yaml` to point at an alternate module layout or to toggle module defaults.

## Example Output & Observability

A successful `--mode score` run prints JSON similar to the following:

```json
{
  "backtest": {
    "alpha": 0.18,
    "status": "ok",
    "trades": 12
  },
  "embeddings": {
    "embedded_rows": 24,
    "status": "ok"
  },
  "fingerprints": {
    "created": 12,
    "status": "ok"
  },
  "ingest": {
    "inserted_filings": 6,
    "status": "ok"
  },
  "scans": {
    "matches": 5,
    "status": "ok"
  }
}
```

- Prefect server logs live under `~/.prefect/logs` by default; view per-flow runs in the UI or with `prefect deployment ls` / `prefect flow-run ls`.
- Pipeline-specific logging streams to stdout; add `--no-fail-fast` when debugging to collect all module errors in one run.

## Platform Coverage

- **Local virtualenv:** Follow the Quickstart commands as written—everything runs on `localhost` with the `.venv` you created.
- **GitHub Codespaces:** Use the same steps but export environment variables via Codespaces secrets, expose ports `4200`, `54321`, and `54323`, and start Prefect with `--host 0.0.0.0`.
- **Docker-based workers:** The default Prefect work pool (`my-docker-pool`) is configured for Docker images. Start `prefect agent start -q my-docker-pool` or run a Docker worker so scheduled deployments can execute inside containers.

With Supabase running, Prefect deployed, and the environment variables in place, the insider-trading flow will ingest seed filings, build features, update embeddings, fingerprint signals, execute similarity scans, and backtest end-to-end.
