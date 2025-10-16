# Prefect Flows & Deployments

## Discovered `@flow` Entrypoints
| Flow Function | File | Parameters (signature) |
| --- | --- | --- |
| `compute_offexchange_features` | `flows/compute_offexchange_features.py` | `(trade_date: date, symbols: Sequence[str] | None = None, persist: bool = True)` |
| `compute_intraday_features` | `flows/compute_intraday_features.py` | `(trade_date: date | None = None, symbols: Sequence[str] | None = None, persist: bool = False)` |
| `fingerprint_vectorization` | `flows/embeddings_and_fingerprints.py` | `(asset_symbol: str | None = None, embedder_configs: Sequence[dict[str, Any]] = (), numeric_features: str | None = None, feature_columns: Sequence[str] = (), metadata_columns: Sequence[str] = (), timestamps: Sequence[str] = (), base_metadata: Mapping[str, Any] | None = None, target_dim: int = 128, use_pca: bool = True, table_name: str = 'signal_fingerprints')` |
| `supabase_embedding_refresh` | `flows/embedding_flow.py` | `(limit: int = 10)` |
| `ingest_form4` | `flows/ingest_sec_form4.py` | `(date_from: date | None = None, date_to: date | None = None, persist: bool = True)` |
| `scheduled_backtest_runner` | `flows/backtest_flow.py` | `(limit: int = 3)` |
| `insider_prefiling_backtest` | `flows/backtest.py` | `(config: dict[str, Any] | None = None)` |
| `scheduled_vector_prune` | `flows/prune_flow.py` | `(max_age_days: int = 120, min_t_stat: float = 0.25, regime_diversity: int = 2)` |
| `similarity_scan_flow` | `flows/similarity_scans.py` | `(query_path: str | Path | None = None, k: int = 5, output_dir: str | Path = 'reports/similarity', user_filters: Mapping[str, Any] | None = None, allow_cross_symbol: bool = False)` |

## Prefect Deployment Definitions
`prefect.yaml` defines nine deployments (embedding refresh, scheduled backtest, nightly prune, SEC ingest, off-exchange, intraday, fingerprints, similarity scans, insider backtest) targeting the `local-agent` work pool with interval/cron schedules commented where not finalised.

## Runtime Status
Running `prefect deployments ls` against the bundled Prefect 3.4.24 CLI starts an ephemeral server but returns no registered deployments, indicating they have not been pushed yet.
