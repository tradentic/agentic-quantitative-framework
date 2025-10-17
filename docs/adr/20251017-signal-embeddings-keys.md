# ADR: Signal Embedding Keys and Versioning

- **Status:** Accepted
- **Date:** 2025-10-17
- **Context:**
  - The `signal_embeddings` table previously enforced idempotency on `(asset_symbol, time_range)` only.
  - Multiple embedding generators (TS2Vec, DeepLOB, etc.) now write vectors for the same asset/time window.
  - We need deterministic upserts per embedding family while preserving coexisting variants.
- **Decision:**
  - Introduce non-null `emb_type` and `emb_version` columns with canonical defaults (`ts2vec` / `v1`).
  - Enforce uniqueness on `(asset_symbol, time_range, emb_type, emb_version)`.
  - Extend the Supabase client helpers, flows, and seeds to populate these attributes and refresh `updated_at` during upserts.
  - Add regression tests ensuring repeated writes update in place and distinct embedding types coexist.
- **Consequences:**
  - Existing ingestion paths remain idempotent by default (TS2Vec rows inherit the canonical defaults).
  - New embedding writers must explicitly version their payloads to avoid conflicts.
  - Historical rows automatically backfill the canonical defaults during the migration.
