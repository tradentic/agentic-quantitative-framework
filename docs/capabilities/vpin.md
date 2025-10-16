# VPIN / Flow Toxicity

## Motivation
- Detect informed trading pressure around filing or event windows by tracking volume-synchronised order flow imbalance.
- Provide an interpretable toxicity metric that complements microstructure diagnostics and supports alerting in compliance or alpha workflows.

## Inputs / Outputs
- **Inputs**: Trade prints with `symbol`, `date`, `window`, `timestamp`, `price`, and `size` columns.
- **Outputs**: Aggregated frame containing `vpin`, `vpin_change`, `vpin_obs`, and `vpin_qc_pass` per `(symbol, date, window)` grouping. Column names, dtypes, and units are formalized in the [feature data contract](../specs/FEATURE_CONTRACTS.md#compute_vpin).

## Configs
- `bucket_volume`: volume threshold for completing a VPIN bar (e.g., 50k shares).
- `rolling_bars`: number of completed bars used to compute the VPIN rolling average.
- Ensure timestamps are timezone-aware or normalized prior to ingestion.

## CLI Examples
```bash
python -c "import pandas as pd; from features.vpin import compute_vpin; df = pd.read_parquet('trades.parquet'); print(compute_vpin(df, bucket_volume=5000, rolling_bars=20))"
```

## Failure Modes
- Insufficient trades to fill even a single volume bar; returns NaNs and `vpin_qc_pass=False`.
- Trade feeds without price variation cause the tick rule to default to buy flow, biasing VPIN upward.
- Non-positive `bucket_volume` or `rolling_bars` raise `ValueError`.

## Validation Checks
- Synthetic balanced order flow should yield VPIN ≈ 0 after rolling warm-up.
- Injecting directional volume must elevate VPIN, signalling toxicity.
- Monitor `vpin_obs` to confirm enough bars contribute to the statistic before interpreting alerts.
