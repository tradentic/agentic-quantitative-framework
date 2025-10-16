# Supabase Schema Review

## Extensions
- `vector`, `pgcrypto`, and `btree_gist` enabled via bootstrap migration.【F:supabase/migrations/20240101000000_setup_pgvector.sql†L1-L4】
- Later LangGraph alignment migration also ensures `uuid-ossp` and `vector` are available for embedding workloads.【F:supabase/migrations/20240901090000_align_langgraph_supabase_schema.sql†L1-L23】

## Core Tables & Indexes
- **signal_embeddings** — UUID PK with pgvector(128), GIST time index, and HNSW cosine index; lacks uniqueness on `(asset_symbol, time_range)` so repeated ingests will create new rows when IDs are regenerated.【F:supabase/migrations/20240101001000_baseline_schema.sql†L4-L23】【F:supabase/migrations/20240901090000_align_langgraph_supabase_schema.sql†L6-L35】
- **signal_embeddings_archive** — archival table mirroring embedding schema for retention.【F:supabase/migrations/20240101001000_baseline_schema.sql†L21-L32】
- **feature_registry** — unique `(name, version)` index plus metadata JSON for feature proposals.【F:supabase/migrations/20240101001000_baseline_schema.sql†L33-L45】
- **backtest_results** — stores strategy metrics and artefact pointers; inserted through agent tooling.【F:supabase/migrations/20240101001000_baseline_schema.sql†L46-L61】
- **agent_state & embedding_jobs** — support long-lived agent memory and async embedding queues.【F:supabase/migrations/20240101001000_baseline_schema.sql†L62-L83】
- **edgar_filings** — filings table augmented with symbol, reporter fields, SHA-256 hashes, and provenance JSON to support insider workflows.【F:supabase/migrations/20250101000000_core_schema.sql†L6-L24】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L5-L23】
- **insider_transactions** — enriched with accession number/code keys and unique constraint to prevent duplicates per filing/date/code/symbol.【F:supabase/migrations/20250101000000_core_schema.sql†L26-L46】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L25-L37】
- **daily_features** — reshaped into wide FINRA table with provenance JSON and unique `(symbol, trade_date)` index.【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L39-L70】
- **signal_fingerprints** — pgvector(128) fingerprint store with identity index across signal/version/asset/window span.【F:supabase/migrations/20250101000000_core_schema.sql†L61-L81】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L56-L88】
- **text_chunks** — vectorised filing text store (1536 dims) for document retrieval workflows.【F:supabase/migrations/20250101000000_core_schema.sql†L83-L98】

## RPCs & Seeds
- RPC migrations exist for embedding refresh and pruning but require Supabase functions (not inspected here).【F:supabase/migrations/20240101002000_rpc_refresh_embeddings.sql†L1-L20】
- Seed script populates demo registry rows and fingerprints, aligned with latest schema columns (e.g., `window_start`, `provenance`).【F:supabase/seed.sql†L1-L76】

## Observations
- Embedding ingest pipeline relies on UUID-generated IDs; without deterministic IDs or unique constraints, idempotent backfills are not guaranteed.【F:framework/supabase_client.py†L109-L184】
- Fingerprint table enforces uniqueness, but `signal_embeddings` currently does not, so deduplication strategy should be clarified.
- Provenance columns exist across filings/daily features/fingerprints, supporting auditability.
