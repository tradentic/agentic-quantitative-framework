| Capability | Status | Evidence |
| --- | --- | --- |
| Vector store (pgvector) | ✅ | `signal_embeddings` + HNSW index defined in migrations.【F:supabase/migrations/20240901090000_align_langgraph_supabase_schema.sql†L6-L35】 |
| TS embeddings (TS2Vec) | ⚠️ | `generate_ts2vec_features` provides fallback identity embeddings when ts2vec is missing.【F:features/generate_ts2vec_embeddings.py†L40-L94】 |
| MiniRocket embeddings | ❌ | Module imports fail under NumPy 2.0 due to `np.float_` alias removal.【F:features/minirocket_embeddings.py†L1-L83】【df0c09†L71-L79】 |
| DeepLOB embeddings | ⚠️ | Implemented with lazy torch import; requires optional `torch` dependency and external weights.【F:features/deeplob_embeddings.py†L1-L199】 |
| Microstructure metrics | ✅ | Feature module defines OFI, spreads, Kyle’s lambda with explicit column contracts.【F:features/microstructure.py†L1-L200】 |
| VPIN | ✅ | Volume-bar generator and VPIN computation provided with qc flags.【F:features/vpin.py†L1-L197】 |
| Matrix profile | ⚠️ | `compute_matrix_profile_metrics` depends on `stumpy`/numba; synthetic run stalled during compilation.【F:features/matrix_profile.py†L31-L89】【114788†L1-L73】 |
| Change-points | ✅ | PELT + BOCPD helpers returning rich dataclass outputs.【F:features/change_points.py†L29-L120】 |
| Hawkes features | ✅ | Exponential Hawkes fitting with branching ratio diagnostics implemented.【F:features/hawkes_features.py†L1-L200】 |
| Use-case glue | ✅ | Insider trading pipeline orchestrates modules/config/CLI integration.【F:use_cases/insider_trading/pipeline.py†L1-L200】 |
| Backtests | ✅ | Prefect flow + agent tool for backtests with artefact persistence.【F:flows/backtest.py†L1-L120】【F:agents/tools.py†L56-L116】 |
| Similarity scans | ✅ | Prefect flow orchestrates pgvector similarity scans and reporting.【F:flows/similarity_scans.py†L1-L334】 |
| Provenance | ✅ | Provenance utilities hash metadata and persist via Supabase upsert.【F:framework/provenance.py†L1-L77】 |
| Idempotency | ⚠️ | Embedding upsert uses new UUIDs without deterministic conflict key, risking duplicate rows.【F:framework/supabase_client.py†L109-L184】 |
