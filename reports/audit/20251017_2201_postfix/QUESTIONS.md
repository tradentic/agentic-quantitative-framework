# Open Questions / Blockers

1. **Supabase/Postgres connectivity** — Can you supply `SUPABASE_URL` and either `SUPABASE_SERVICE_ROLE_KEY` or `DATABASE_URL` so we can run catalog queries, idempotent `signal_embeddings` upsert tests, provenance inserts, and similarity scans?【fdbed8†L1-L2】
2. **DeepLOB weights** — Should we expect a `DEEPLOB_WEIGHTS_PATH` for optional inference validation, or is omission intentional for CPU-only deployments?【fdbed8†L1-L2】
3. **Prefect control plane** — Which Prefect API endpoint should we target to list deployments? The local temporary server used by `prefect deployments ls` returned an empty table.【c5db66†L1-L8】
