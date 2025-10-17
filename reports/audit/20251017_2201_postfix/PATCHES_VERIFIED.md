# Patches Verified

- ⚠️ **Provenance table available but not exercised** — Migration creates `provenance_events`, yet insert/select testing awaits database credentials.【F:supabase/migrations/20251017000000_create_provenance_events.sql†L1-L9】【fdbed8†L1-L2】
- ⚠️ **Idempotent `signal_embeddings` indexes in place, runtime upsert pending** — Unique key now covers `(asset_symbol, time_range, emb_type, emb_version)`; duplicate-write smoke test blocked without DB access.【F:supabase/migrations/20251017010000_signal_embeddings_idempotent.sql†L1-L27】【fdbed8†L1-L2】
- ✅ **Prefect deployment entrypoints map to live flows** — All `prefect.yaml` deployments import successfully, including `compute-intraday` → `flows/compute_intraday_features.py:compute_intraday_features`.【F:prefect.yaml†L1-L78】【636172†L1-L4】
- ✅ **MiniRocket remains NumPy≥2.0 safe** — Module import succeeded and dependency checks degrade gracefully when `sktime` is missing.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L277-L282】【f8fd4b†L1-L1】
- ✅ **PCA fingerprint pipeline outputs 128-d vectors** — Artifact refreshed to 128 components and projector validated via `project_to_fingerprint_width` and audit script.【c3f0fc†L1-L2】【904270†L1-L4】
- ✅ **Matrix Profile falls back cleanly when Numba path unavailable** — `engine='numba'` call on a small window forced the naive implementation without errors.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L14-L20】
- ✅ **DeepLOB optionality upheld** — Import works and attempting inference without Torch raises `DependencyUnavailable`, matching expectations for optional weights/device configuration.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L283-L286】【f8fd4b†L1-L2】
- ✅ **Feature data contracts enforced** — TS2Vec fallback emits padded 128-d embeddings honoring `EmbeddingRecord` validation rules.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L128-L276】【65cd06†L1-L4】
- ✅ **Vector-dimension CI validator runnable offline** — `scripts/audit_vector_dims.py` loads the 128-d PCA reducer and skips Supabase inspection gracefully when credentials are absent.【904270†L1-L4】
