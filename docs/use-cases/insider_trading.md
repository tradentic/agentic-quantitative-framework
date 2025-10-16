# Insider Trading Pipeline

## Motivation
- Provide a single command entry point that orchestrates SEC Form 4 ingestion, market microstructure feature engineering, embedding refreshes, fingerprint materialization, similarity scans, and backtest scheduling.
- Standardize how analyst teams experiment with insider trading hypotheses without duplicating glue code across notebooks or flows.
- Enable dry-run (mock) execution so developers can verify orchestration locally without vendor credentials.

## Inputs and Outputs
- **Inputs**
  - Pipeline mode (`train`, `score`, or `refresh`).
  - Trade date or date range (optional for some modules).
  - Optional symbol universe to constrain feature or scan steps.
  - YAML configuration (`use_cases/insider_trading/config.yaml`) describing default options per module and mode.
- **Outputs**
  - JSON summary per module, including status (`ok`, `skipped`, `mocked`, `error`) and module-specific metadata (e.g., number of filings ingested, rows computed, jobs processed).
  - Structured logging that captures which modules ran, which were disabled, and whether mocks were used.

## Configuration
- Defaults live in [`use_cases/insider_trading/config.yaml`](../../use_cases/insider_trading/config.yaml).
- Each module (e.g., `sec_ingest`, `market_features`, `embeddings`) can be enabled/disabled globally and per-mode.
- Module options support overrides such as `days_back`, `persist`, `limit`, `mock`, and `fingerprint_size`.
- The CLI flag `--mock` forces mock execution for all modules regardless of configuration.
- Custom configuration files can be supplied via `--config path/to/config.yaml`.

## CLI Examples
- Score a single session using the default configuration:
  ```bash
  python -m use_cases.insider_trading.pipeline --mode score --date 2025-01-15
  ```
- Run a refresh with explicit date range and mock disabled:
  ```bash
  python -m use_cases.insider_trading.pipeline --mode refresh --date-from 2025-01-01 --date-to 2025-01-07 --no-fail-fast
  ```
- Execute the training pipeline with a custom configuration file:
  ```bash
  python -m use_cases.insider_trading.pipeline --mode train --config my_overrides.yaml
  ```

## Failure Modes
- **Configuration errors**: malformed YAML or undefined modes raise a descriptive exception before execution.
- **Missing modules**: if a mode references an unregistered module, the pipeline raises an error (or records it when `--no-fail-fast` is used).
- **External service outages**: modules that interact with SEC, FINRA, or Supabase can be mocked via configuration or the `--mock` flag to avoid runtime failures.
- **Invalid dates**: incorrectly formatted `--date`/`--date-from`/`--date-to` arguments raise parsing errors before the pipeline runs.

## Validation Checks
- Unit tests cover configuration loading, module enablement logic, and failure handling of the runtime orchestrator.
- The pipeline prints structured JSON for downstream monitoring or notebook inspection.
- Logs provide traceability for each module invocation, including mock/skipped states and parameterization.
