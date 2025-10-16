# Insider Trading Pipeline

## Motivation
- Provide a single command entry point that orchestrates SEC Form 4 ingestion, market microstructure feature engineering, embedding refreshes, fingerprint materialization, similarity scans, and backtest scheduling.
- Standardize how analyst teams experiment with insider trading hypotheses without duplicating glue code across notebooks or flows.
- Enable dry-run (mock) execution so developers can verify orchestration locally without vendor credentials.

## Inputs and Outputs
- **Inputs**
  - Pipeline mode (`train`, `score`, or `refresh`).
  - Trade date or date range (optional for some modules).
  - Optional symbol universe to constrain feature, fingerprint, and scan steps.
  - YAML configuration (`use_cases/insider_trading/config.yaml`) describing default options per module and mode (signal names, fingerprint window, similarity `top_k`, etc.).
- **Outputs**
  - JSON summary per module, including status (`ok`, `skipped`, `mocked`, `error`) and module-specific metadata (e.g., number of filings ingested, features persisted, fingerprints generated, matches returned).
  - Structured logging that captures which modules ran, which were disabled, and whether mocks were used.

## Configuration
- Defaults live in [`use_cases/insider_trading/config.yaml`](../../use_cases/insider_trading/config.yaml).
- Each module (e.g., `sec_ingest`, `market_features`, `embeddings`) can be enabled/disabled globally and per-mode.
- Module options support overrides such as `days_back`, `persist`, `limit`, `mock`, and `fingerprint_size`.
- The CLI flag `--mock` forces mock execution for all modules regardless of configuration.
- Custom configuration files can be supplied via `--config path/to/config.yaml`.

## Pipeline Modules
1. **`sec_ingest`** – Downloads Form 4 filings, extracts transactions, and upserts `edgar_filings`/`insider_transactions` with provenance hashes.
2. **`market_features`** – Calls the FINRA off-exchange flow to compute `daily_features` (short volume / ATS metrics) and record provenance JSON.
3. **`embeddings`** – Optional queue-based embedding refresh (unchanged).
4. **`fingerprints`** – Materializes signal fingerprints via `fingerprint_vectorization`, validating `window_start/window_end`, computing `fingerprint_sha256`, and persisting to `signal_fingerprints`.
5. **`scans`** – Executes similarity searches using freshly generated fingerprints and returns match dictionaries per symbol.
6. **`backtest`** – Drains pending backtest requests when training mode is active.

## CLI Examples
- Score a single session for a specific symbol using mocks for market data:
  ```bash
  python -m use_cases.insider_trading.pipeline --mode score --date 2025-01-15 --symbol ACME --mock
  ```
- Run a refresh with explicit date range and real feature/fingerprint persistence:
  ```bash
  python -m use_cases.insider_trading.pipeline --mode refresh --date-from 2025-01-01 --date-to 2025-01-07 --symbol ACME --symbol BETA
  ```
- Execute the training pipeline with a custom configuration file:
  ```bash
  python -m use_cases.insider_trading.pipeline --mode train --config my_overrides.yaml --date 2025-02-01
  ```

## Failure Modes
- **Configuration errors**: malformed YAML or undefined modes raise a descriptive exception before execution.
- **Missing modules**: if a mode references an unregistered module, the pipeline raises an error (or records it when `--no-fail-fast` is used).
- **External service outages**: modules that interact with SEC, FINRA, or Supabase can be mocked via configuration or the `--mock` flag to avoid runtime failures.
- **Invalid dates**: incorrectly formatted `--date`/`--date-from`/`--date-to` arguments raise parsing errors before the pipeline runs.

## Validation Checks
- Unit tests cover configuration loading, module enablement logic, and failure handling of the runtime orchestrator.
- Additional tests (`tests/use_cases/test_insider_pipeline.py`) mock Supabase to confirm fingerprint and similarity modules build schema-aligned payloads.
- The pipeline prints structured JSON for downstream monitoring or notebook inspection.
- Logs provide traceability for each module invocation, including mock/skipped states and parameterization.
