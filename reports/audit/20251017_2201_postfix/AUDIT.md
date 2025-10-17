# Post-Fix Verification Audit — 2025-10-17 22:01 UTC

## Top Findings
- ✅ **Feature generators execute deterministically on synthetic data.** Matrix profile, change-point, Hawkes, microstructure, VPIN, and TS2Vec modules all produced finite outputs on toy inputs, with TS2Vec falling back to identity embeddings while preserving the 128-d contract.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L2-L127】【F:reports/audit/20251017_2201_postfix/feature_checks.json†L128-L275】
- ✅ **Prefect deployment map matches code entrypoints.** Every deployment declared in `prefect.yaml` resolves to an importable `@flow` function, and `compute-intraday` targets the intraday flow module as expected.【F:prefect.yaml†L1-L78】【636172†L1-L4】
- ✅ **MiniRocket PCA pipeline is bootstrapped at 128 dimensions.** The PCA artifact was (re)fit to 128 components and `scripts/audit_vector_dims.py` confirms the reducer width while Supabase checks are skipped when credentials are absent.【c3f0fc†L1-L2】【904270†L1-L4】
- ⚠️ **Database-level verification blocked by missing Supabase/Postgres credentials.** Required variables (`SUPABASE_URL`, `DATABASE_URL`, `DEEPLOB_WEIGHTS_PATH`, `DEEPLOB_DEVICE`) are absent, preventing catalog inspection, idempotent upsert smoke tests, provenance round-trips, and similarity scan exercises; placeholders remain documented in migrations only.【fdbed8†L1-L2】【F:supabase/migrations/20240101000000_setup_pgvector.sql†L1-L5】【F:supabase/migrations/20250101000000_core_schema.sql†L1-L49】【F:supabase/migrations/20251016_idempotency.sql†L1-L21】
- ⚠️ **Prefect CLI lists no registered deployments under the temporary local server.** The CLI spins up an ephemeral API and returns an empty table, suggesting deployments are not registered against the current profile; manual `prefect deploy` may still be required in this environment.【c5db66†L1-L8】

## Next Actions
1. Provide Supabase/Postgres connection details (or launch the Supabase stack) so provenance inserts, vector idempotency, and similarity scans can be validated end-to-end.
2. Register Prefect deployments against the intended API (or point CLI at the authoritative server) to confirm scheduler parity instead of relying on ephemeral defaults.
3. Once credentials are available, re-run idempotent `signal_embeddings` upsert smoke tests and provenance logging to finalize the audit.
