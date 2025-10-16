# Insider Pre-Filing Classifier Backtest

## Motivation
- Establish a reproducible baseline for insider trading detection when Form 4 filings arrive shortly after an observed feature window.
- Quantify whether simple gradient boosted models can separate likely pre-filing windows from negatives before investing in heavier architectures.
- Produce artefacts (metrics + plots) that downstream agents can consume for further experimentation.

## Inputs / Outputs
- **Inputs**
  - Windowed feature table (CSV/Parquet) with `symbol`, `window_end`, and numeric features.
  - Form 4 filing table (CSV/Parquet) with `symbol` and `filing_date` columns.
- **Outputs**
  - JSON metrics report saved under `reports/backtests/` including configuration, per-model metrics, and calibration data.
  - ROC, precision-recall, and calibration plots (PNG) sharing the timestamped prefix of the metrics file.
  - Return value: `BacktestArtifacts` dataclass pointing to all generated files.

## Configurations
- `InsiderBacktestConfig` accepts paths plus knobs for horizon (`label_horizon_days`), validation split (`validation_fraction`), calibration bins, and random seed.
- Feature columns are inferred as numeric columns not listed in `{symbol, window_end, filing columns, label}`.
- Baselines prefer XGBoost + LightGBM; when those libraries are absent, the flow degrades gracefully to logistic regression while noting the fallback inside the metrics report.

## CLI Example
```python
from pathlib import Path

from flows.backtest import InsiderBacktestConfig, insider_prefiling_backtest

config = InsiderBacktestConfig(
    windows_path=Path("data/windows.parquet"),
    filings_path=Path("data/form4.csv"),
    label_horizon_days=5,
    validation_fraction=0.2,
)

artifacts = insider_prefiling_backtest(config)
print(artifacts.metrics_path)
```

## Failure Modes
- Missing or malformed datetime columns trigger `ValueError` during coercion.
- Lack of numeric feature columns raises `ValueError` before model training.
- If both XGBoost and LightGBM are unavailable, logistic regression fallback ensures the flow still completes, but metrics should be interpreted as weaker baselines.
- File resolution errors yield `FileNotFoundError`.

## Validation Checks
- Unit tests cover label generation, time-based splitting, and the end-to-end flow on CSV/Parquet inputs.
- Metrics JSON embeds calibration data enabling external verification of probability quality.
- Deterministic splits (seed + chronological cutoff) keep runs reproducible given the same datasets.
