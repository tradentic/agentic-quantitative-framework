## Prefect Deployments

| Name | Flow Name | Entrypoint | Schedule |
| --- | --- | --- | --- |
| embedding-refresh-dev | supabase-embedding-refresh | flows/embedding_flow.py:supabase_embedding_refresh | interval: 600s |
| scheduled-backtest-dev | scheduled-backtest-runner | flows/backtest_flow.py:scheduled_backtest_runner | interval: 900s |
| nightly-prune-dev | scheduled-vector-prune | flows/prune_flow.py:scheduled_vector_prune | cron: 0 3 * * * |
| ingest-sec-form4 | ingest-sec-form4 | flows/ingest_sec_form4.py:ingest_form4 | {} |
| compute-offexchange | compute-offexchange-features | flows/compute_offexchange_features.py:compute_offexchange_features | {} |
| compute-intraday | compute-offexchange-features | flows/compute_offexchange_features.py:compute_offexchange_features | {} |
| fingerprints | fingerprint-vectorization | flows/embeddings_and_fingerprints.py:fingerprint_vectorization | {} |
| similarity-scans | signal-similarity-scan | flows/similarity_scans.py:similarity_scan_flow | {} |
| backtest | insider-prefiling-classifier-backtest | flows/backtest.py:insider_prefiling_backtest | {} |

## Discovered `@flow` Entrypoints

| File | Flow Functions |
| --- | --- |
| flows/__init__.py | — |
| flows/backtest.py | insider_prefiling_backtest |
| flows/backtest_flow.py | scheduled_backtest_runner |
| flows/compute_offexchange_features.py | compute_offexchange_features |
| flows/embedding_flow.py | supabase_embedding_refresh |
| flows/embeddings_and_fingerprints.py | fingerprint_vectorization |
| flows/ingest_sec_form4.py | ingest_form4 |
| flows/prune_flow.py | scheduled_vector_prune |
| flows/similarity_scans.py | similarity_scan_flow |
