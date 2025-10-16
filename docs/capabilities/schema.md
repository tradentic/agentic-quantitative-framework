# Supabase Core Schema & Seeds

## Motivation
- Provide normalized storage for SEC filings, insider transactions, engineered features, and embedding fingerprints.
- Enable deterministic migrations so `supabase db reset --local` rebuilds the vector-enabled schema for local agents.
- Ship a demo vector row to validate pgvector dimensions and Supabase CLI seed workflows.

## Inputs & Outputs
- **Inputs:**
  - Supabase migration runner executes `supabase/migrations/20250101000000_core_schema.sql`.
  - Seed execution reads `sql/seed_vector.sql` during `supabase db reset --local`.
- **Outputs:**
  - Tables: `edgar_filings`, `insider_transactions`, `daily_features`, `signal_fingerprints`, `text_chunks`.
  - One `signal_fingerprints` row populated with a 128-dimension vector for smoke testing.

## Configuration
- Requires Supabase project with `pgvector`, `pgcrypto`, and `btree_gist` extensions enabled (handled by migrations).
- Optional tuning via environment variables:
  - `PGVECTOR_IVFFLAT_LISTS` to override default list count when re-indexing fingerprints.
  - `SUPABASE_SEED_FILE` can be pointed at `sql/seed_vector.sql` for custom workflows.

## CLI Examples
- Reset database and apply schema: `supabase db reset --local`.
- Apply only migrations: `supabase db push --included-only supabase/migrations/20250101000000_core_schema.sql`.
- Re-run seed independently: `psql "$SUPABASE_DB_URL" -f sql/seed_vector.sql`.

## Failure Modes
- Missing pgvector extension leading to `type "vector" does not exist` during migration.
- Re-seeding without migrations causes conflict if the table is absent; run migrations first.
- Non-128-length vectors will error with `dimension mismatch`; keep seed values at 128 elements.

## Validation Checks
- After reset, verify table creation: `\dt+ public.signal_fingerprints` inside `psql` session.
- Confirm seed row count: `select count(*) from public.signal_fingerprints;` should return `1` on fresh reset.
- Validate vector dimension: `select vector_dims(fingerprint) from public.signal_fingerprints limit 1;`.
