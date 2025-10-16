# Supabase Schema Check

## Extensions
- `vector`, `pgcrypto`, and `btree_gist` enabled in `20240101000000_setup_pgvector.sql` to support pgvector indexes and UUID helpers.

## Core Tables & Columns
- **signal_embeddings** (`20240101001000_baseline_schema.sql`): UUID PK, `asset_symbol`, `tstzrange time_range`, `vector(128) embedding`, metadata columns, IVFFlat index plus archive table.
- **feature_registry** and **backtest_results** provide metadata tracking for agent-generated artifacts (`20240101001000_baseline_schema.sql`).
- **edgar_filings** / **insider_transactions** / **daily_features** / **signal_fingerprints** introduced in `20250101000000_core_schema.sql`; later alignment migration (`20250301090000_align_insider_pipeline_schema.sql`) renames `feature_date → trade_date`, injects provenance JSON, adds `asset_symbol/window_start` to `signal_fingerprints`, and rebuilds unique indexes.
- **text_chunks** holds 1,536-dim embeddings for filing text (`20250101000000_core_schema.sql`).
- **signal_embeddings triggers/RPCs**: update/notify triggers and prune RPC defined under `20240101003000_rpc_prune_vectors.sql` and `20240101004000_signal_embedding_triggers.sql`.

## Idempotency & Constraints
- `20251016_idempotency.sql` enforces `daily_features(symbol, trade_date, feature_version)` and `signal_fingerprints(asset_symbol, window_start, window_end, version)` uniqueness; adds upsert guard for `signal_embeddings`.
- `20260101080000_enforce_fingerprint_width.sql` keeps `signal_fingerprints.fingerprint` at `vector(128)`.

## Seeds
- `supabase/seed.sql` populates demo rows across embeddings, filings, daily features, and fingerprints to validate migrations end-to-end.

## Gaps & Risks
- No migration creates the `provenance_events` table expected by `framework/provenance.py`; provenance writes will fail until added.
- Align/idempotency migrations assume prior renames executed; fresh database must apply migrations sequentially to avoid mixed column names (`feature_date` vs `trade_date`).
- Hawkes/microstructure outputs expect `daily_features` provenance JSON; ensure Supabase row-level security accommodates the new fields.
