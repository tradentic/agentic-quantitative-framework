# Schema Check

## Extension & Global Prerequisites
- `create extension if not exists vector;` remains codified in the bootstrap migration (static verification only; runtime check blocked by missing DB credentials).【F:supabase/migrations/20240101000000_setup_pgvector.sql†L1-L5】【fdbed8†L1-L2】

## Core Tables (DDL Review)
- **`signal_embeddings`** — UUID PK, `embedding vector(128)`, time range and metadata columns; IVFFlat/HNSW indexes plus updated unique key on `(asset_symbol, time_range, emb_type, emb_version)`.【F:supabase/migrations/20240101001000_baseline_schema.sql†L1-L29】【F:supabase/migrations/20251017010000_signal_embeddings_idempotent.sql†L1-L27】
- **`signal_fingerprints`** — Renamed columns `(id, window_start, window_end)` with enforced `vector(128)` width and unique identity `(signal_name, version, asset_symbol, window_start, window_end)`.【F:supabase/migrations/20250101000000_core_schema.sql†L30-L64】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L40-L143】【F:supabase/migrations/20260101080000_enforce_fingerprint_width.sql†L1-L5】
- **`daily_features`** — FINRA-aligned layout (no `feature_key`), with unique `(symbol, trade_date, feature_version)` index for idempotent upserts.【F:supabase/migrations/20250101000000_core_schema.sql†L13-L38】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L40-L104】【F:supabase/migrations/20251016_idempotency.sql†L1-L11】
- **`provenance_events`** — Append-only provenance log capturing `source`, `payload`, `artifact_sha256`, `parser_version`, and timestamps.【F:supabase/migrations/20251017000000_create_provenance_events.sql†L1-L9】

## Idempotency & Upsert Targets
- Unique indexes codified for `daily_features`, `signal_fingerprints`, and `signal_embeddings`; runtime duplicate-insert smoke tests remain pending until database connectivity is available.【F:supabase/migrations/20251016_idempotency.sql†L1-L21】【F:supabase/migrations/20251017010000_signal_embeddings_idempotent.sql†L1-L27】

## Vector Dimension Discipline
- PCA artifact re-fit to 128 components and vector audit script confirms reducer width while skipping Supabase inspection (0 rows fetched).【c3f0fc†L1-L2】【904270†L1-L4】
- `EmbeddingRecord` Pydantic validator rejects non-128d payloads, providing application-level guardrails for pgvector writes.【65cd06†L1-L4】

## Pending Runtime Checks
- Catalog queries, pgvector extension verification, idempotent upsert smoke tests, provenance inserts, and similarity scan SQL calls were **not** executed because the environment lacks `SUPABASE_URL` / `DATABASE_URL`. Restore credentials to complete these end-to-end checks.【fdbed8†L1-L2】
