# Microstructure Feature Capability

## Motivation
- Quantify intraday liquidity and order flow pressure using trades and NBBO windows.
- Provide window-level metrics that are robust to outliers and sparse updates.
- Supply QC flags so downstream models can filter unreliable windows.

## Inputs
- Quotes DataFrame (`symbol`, `date`, `window`, `timestamp`, `bid_price`, `bid_size`, `ask_price`, `ask_size`).
- Trades DataFrame (`symbol`, `date`, `window`, `timestamp`, `price`, `size`).
- Optional parameters: none; all functions infer alignment from timestamps.

## Outputs
- Order flow imbalance (`compute_ofi`) with observation counts and QC flags.
- Closing book imbalance (`book_imbalance`).
- Kyle's λ slope estimate (`kyle_lambda`) aligned to NBBO mid-prices.
- Amihud ILLIQ ratio (`amihud_illiq`).
- Absolute/relative spreads (`spreads`).
- All functions return one row per `(symbol, date, window)` with numeric fields plus `_qc_pass` booleans.
- Schema, dtypes, and unit hints are defined in the [feature data contract](../specs/FEATURE_CONTRACTS.md#microstructure-features).

## Configuration & Usage Notes
- Ensure timestamps are timezone-aware or consistent across trades and quotes before calling the functions.
- `kyle_lambda` uses backward-looking NBBO alignment via `pandas.merge_asof`; pre-sort inputs for performance.
- Set environment locale/timezone via `TZ` if using naive timestamps across regions.

## CLI Examples
- Run the feature tests: `python -m pytest tests/features/test_microstructure.py`.
- Ad-hoc run within the repo:
  ```bash
  python - <<'PY'
  import pandas as pd
  from features import microstructure
  quotes = pd.read_parquet('quotes.parquet')
  trades = pd.read_parquet('trades.parquet')
  print(microstructure.compute_ofi(quotes))
  print(microstructure.kyle_lambda(trades, quotes))
  PY
  ```

## Failure Modes & Retries
- Missing required columns raise `ValueError` before computation.
- Empty inputs return empty DataFrames with correctly typed columns.
- Windows without NBBO context yield `NaN` metrics and `False` QC flags.

## Validation Checks
- Unit tests under `tests/features/test_microstructure.py` validate metric ranges and QC flags on synthetic data.
- Additional spot checks can compare QC flags against raw observation counts before modeling.
