# Capability Matrix

| Capability | Status | Evidence & Notes |
| --- | --- | --- |
| Vector store (pgvector, Supabase wiring) | ⚠️ Partial | Tables, triggers, and RPCs defined, but `provenance_events` table missing and Prefect deployments not pushed; Supabase client requires env secrets. |
| TS embeddings (TS2Vec, identity fallback) | ⚠️ Partial | `generate_ts2vec_features` falls back to identity because `ts2vec` module absent; 128-d padding works but true encoder unavailable. |
| MiniRocket embeddings | ⚠️ Partial | Module present yet raises `DependencyUnavailable` without `sktime`; no fallback path. |
| DeepLOB embeddings | ⚠️ Partial | Loader implemented but needs `torch` and weights; current environment raises dependency error. |
| Microstructure metrics | ✅ Ready | Multiple metrics (`compute_ofi`, `spreads`, etc.) validated with synthetic data. |
| VPIN | ✅ Ready | `compute_vpin` executed on synthetic trades and produced QC-passing output. |
| Matrix Profile | ✅ Ready | `compute_matrix_profile_metrics` runs with naive fallback when `stumpy` missing. |
| Change-points | ✅ Ready | `change_point_scores` offline detector operational on synthetic series. |
| Hawkes self-excitation | ✅ Ready | `hawkes_self_excitation_metrics` generates branching ratios from grouped events. |
| Use-case glue (insider pipeline) | ⚠️ Partial | Pipeline/config present but depends on Supabase credentials, FINRA downloads, and PCA artifacts. |
| Backtests | ⚠️ Partial | Prefect flow + agents wired, yet LightGBM/XGBoost optional deps likely missing and deployments not registered. |
| Similarity scans | ⚠️ Partial | Flow + Supabase RPC integration exist, but requires Supabase connectivity and query templates; no packaged sample queries. |
| Provenance | ⚠️ Partial | `framework/provenance` handles hashing, but Supabase migrations lack `provenance_events` table. |
| Idempotency | ⚠️ Partial | Unique indexes added for `daily_features` & `signal_fingerprints`; ensure sequential migration order and Supabase RLS updates to honour new keys. |
