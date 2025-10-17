# Capability Matrix

| Capability | Status | Evidence |
| --- | --- | --- |
| Vector store (pgvector tables & indexes) | ⚠️ Partial | Schema migrations define `vector(128)` embeddings/fingerprints and idempotent indexes, but no live database session was available to confirm extension or upsert behaviour.【F:supabase/migrations/20240101001000_baseline_schema.sql†L1-L29】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L40-L143】【F:supabase/migrations/20251016_idempotency.sql†L1-L21】【fdbed8†L1-L2】 |
| TS2Vec embeddings | ✅ Present | Fallback identity path emitted three 128-d rows with canonical metadata, demonstrating Supabase payload contract compliance.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L128-L276】 |
| MiniRocket embeddings | ⚠️ Partial | Module imports under NumPy≥2.0 but runtime raises `DependencyUnavailable` because `sktime` is not installed; PCA projection validated separately.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L277-L282】【f8fd4b†L1-L1】【c3f0fc†L1-L2】 |
| DeepLOB embeddings | ✅ Optional | Import guard works; requesting embeddings surfaces a controlled `DependencyUnavailable` when Torch/weights are absent.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L283-L286】【f8fd4b†L1-L2】 |
| Microstructure suite | ✅ Present | OFI, book imbalance, Kyle's λ, Amihud illiquidity, and spread metrics produced finite outputs on synthetic data.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L58-L112】 |
| VPIN | ✅ Present | Synthetic volume bars yielded VPIN=1.0 and Δ=0.25 with QC flags true.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L113-L127】 |
| Matrix Profile | ✅ Present | Naive engine executed; numba request gracefully fell back to naive without JIT dependency.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L2-L20】 |
| Hawkes features | ✅ Present | Hawkes fitter converged on toy timestamps with finite parameters.【F:reports/audit/20251017_2201_postfix/feature_checks.json†L46-L56】 |
| Similarity scans / k-NN | ⚠️ Partial | RPC helpers exist but no Supabase connection meant k-NN queries were not executed.【fdbed8†L1-L2】【F:framework/supabase_client.py†L137-L201】 |
| Backtests orchestration | ⚠️ Partial | Backtest flow entrypoint imports cleanly, yet Prefect CLI shows zero registered deployments on the temporary server.【636172†L1-L4】【c5db66†L1-L8】 |
| Provenance logging | ⚠️ Partial | Table DDL present but insert/select round-trip deferred pending database credentials.【F:supabase/migrations/20251017000000_create_provenance_events.sql†L1-L9】【fdbed8†L1-L2】 |
| Idempotent embeddings | ⚠️ Partial | Unique indexes now cover `(asset_symbol, time_range, emb_type, emb_version)` but duplicate insert smoke test cannot run offline.【F:supabase/migrations/20251017010000_signal_embeddings_idempotent.sql†L1-L27】【fdbed8†L1-L2】 |
