# Patch Plan

## Supabase Schema & Provenance
- Author migration `20251020_create_provenance_events.sql` to create `provenance_events` (PK, JSONB meta, timestamps) and grant upsert permissions aligned with `framework/provenance.record_provenance` payload.
- Extend `supabase/seed.sql` with a demo provenance row to validate the new table.
- Update `supabase/migrations/20251016_idempotency.sql` (or follow-up migration) to confirm `daily_features`/`signal_fingerprints` indexes are present after renames; add comments warning about migration order.

## Embedding Tooling
- Document optional dependencies (`ts2vec`, `sktime`, `torch`) in `README.md`/`LOCAL_DEV_SETUP.md` and add extras to `pyproject.toml` (e.g. `[project.optional-dependencies] embeddings = [...]`).
- Provide lightweight smoke tests under `tests/features/` that skip when optional packages missing but assert fallbacks (identity embeddings) behave as expected.
- Consider shipping a small serialized PCA artifact (or generator script) under `artifacts/pca/` for pipeline defaults.

## Prefect Orchestration
- Add a `Makefile` target (e.g. `make prefect-deploy`) that runs `prefect deploy --all --prefect-file prefect.yaml` and document usage.
- Commit templated JSON query under `flows/similarity_scans_examples/` to demonstrate similarity scans.
- Introduce integration tests or CLI dry-run script to validate each flow's parameter schema without hitting external vendors (mock FINRA/Polygon clients).

## Use-Case Pipeline Hardening
- Enhance `use_cases/insider_trading/pipeline.py` with explicit dependency checks (Supabase creds, FINRA endpoints) and graceful warnings when running in `mock` mode.
- Backfill config defaults for missing artifacts (e.g., allow pipeline to skip PCA when artifact not found by toggling `fit_if_missing`).
- Add docs summarizing end-to-end insider workflow (data ingestion → feature generation → embeddings → fingerprints → scans → backtest) and list required secrets per module.
