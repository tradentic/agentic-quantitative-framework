# Prefect Flows & Deployments

## Declared Deployments (`prefect.yaml`)
| Deployment | Entrypoint | Notes |
| --- | --- | --- |
| embedding-refresh-dev | `flows/embedding_flow.py:supabase_embedding_refresh` | Imports successfully as Prefect flow. |
| scheduled-backtest-dev | `flows/backtest_flow.py:scheduled_backtest_runner` | Imports successfully as Prefect flow. |
| nightly-prune-dev | `flows/prune_flow.py:scheduled_vector_prune` | Imports successfully as Prefect flow. |
| ingest-sec-form4 | `flows/ingest_sec_form4.py:ingest_form4` | Imports successfully as Prefect flow. |
| compute-offexchange | `flows/compute_offexchange_features.py:compute_offexchange_features` | Imports successfully as Prefect flow. |
| compute-intraday | `flows/compute_intraday_features.py:compute_intraday_features` | Verified mapping to intraday feature flow (no off-exchange mix-up). |

All entrypoints extracted directly from `prefect.yaml` and validated via dynamic imports.【F:prefect.yaml†L1-L78】【636172†L1-L4】

## CLI Evidence
- `prefect deployments ls` bootstrapped a temporary local API and returned an empty deployment table, indicating that no deployments are registered under the current profile/environment.【c5db66†L1-L8】

## Follow-Ups
1. Point the CLI at the intended Prefect server (or run `prefect deploy`) to confirm that deployments are registered beyond static configuration.
2. Once registered, re-run `prefect deployments ls` to capture the authoritative listing for audit trails.
