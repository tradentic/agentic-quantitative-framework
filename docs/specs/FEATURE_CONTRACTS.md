# Feature Data Contracts

This specification defines the canonical columns, dtypes, and unit hints for feature
frames emitted by the public microstructure and VPIN APIs. Downstream consumers (e.g.
model training pipelines, Supabase ingest jobs, feature stores) should rely on this
contract to validate schemas and select compatible storage types.

Unit hints are normalized tokens so automated checks can reason about semantics:

- `identifier` – categorical symbol identifiers.
- `date` – ISO-8601 trading dates stored as strings.
- `window` – feature window keys (e.g. "pre", "post", "w1").
- `shares` – share count deltas.
- `price` – quote or trade prices in native currency units.
- `price_per_share` – price impact per share (currency/share).
- `ratio` – dimensionless ratio bounded by ±1.
- `probability` – probability-like value between 0 and 1.
- `probability_delta` – change in a probability value (bounded by ±1).
- `count` – integer observation counts.
- `inv_dollar` – inverse currency units (1 / notional).
- `qc_flag` – boolean quality-control indicator.

## Microstructure Features

### `compute_ofi`

| Column | dtype | Unit | Notes |
| --- | --- | --- | --- |
| symbol | object | identifier | Primary symbol key. |
| date | object | date | Trading session date. |
| window | object | window | Intraday aggregation window. |
| ofi | float64 | shares | Net order flow imbalance across the window. |
| ofi_obs | int64 | count | Number of NBBO observations contributing to `ofi`. |
| ofi_qc_pass | bool | qc_flag | QC flag based on observation count and finite result. |

### `book_imbalance`

| Column | dtype | Unit | Notes |
| --- | --- | --- | --- |
| symbol | object | identifier | Primary symbol key. |
| date | object | date | Trading session date. |
| window | object | window | Intraday aggregation window. |
| book_imbalance | float64 | ratio | End-of-window depth imbalance in [-1, 1]. |
| book_imbalance_obs | int64 | count | Number of NBBO observations considered. |
| book_imbalance_qc_pass | bool | qc_flag | QC flag for valid denominator and finite result. |

### `kyle_lambda`

| Column | dtype | Unit | Notes |
| --- | --- | --- | --- |
| symbol | object | identifier | Primary symbol key. |
| date | object | date | Trading session date. |
| window | object | window | Intraday aggregation window. |
| kyle_lambda | float64 | price_per_share | Median price impact per share. |
| kyle_lambda_obs | int64 | count | Matched trade/NBBO observations. |
| kyle_lambda_qc_pass | bool | qc_flag | QC flag when sufficient matched trades exist. |

### `amihud_illiq`

| Column | dtype | Unit | Notes |
| --- | --- | --- | --- |
| symbol | object | identifier | Primary symbol key. |
| date | object | date | Trading session date. |
| window | object | window | Intraday aggregation window. |
| amihud_illiq | float64 | inv_dollar | Amihud illiquidity ratio (|return| / dollar volume). |
| amihud_obs | int64 | count | Number of valid return observations. |
| amihud_qc_pass | bool | qc_flag | QC flag for sufficient valid trades. |

### `spreads`

| Column | dtype | Unit | Notes |
| --- | --- | --- | --- |
| symbol | object | identifier | Primary symbol key. |
| date | object | date | Trading session date. |
| window | object | window | Intraday aggregation window. |
| avg_spread | float64 | price | Mean absolute spread (ask - bid). |
| avg_rel_spread | float64 | ratio | Mean relative spread (spread / mid). |
| spreads_obs | int64 | count | Number of valid NBBO samples. |
| spreads_qc_pass | bool | qc_flag | QC flag for non-zero mid and spread samples. |

## VPIN Features

### `compute_vpin`

| Column | dtype | Unit | Notes |
| --- | --- | --- | --- |
| symbol | object | identifier | Primary symbol key. |
| date | object | date | Trading session date. |
| window | object | window | Intraday aggregation window. |
| vpin | float64 | probability | Rolling VPIN level. |
| vpin_change | float64 | probability_delta | Change in VPIN from the prior bar. |
| vpin_obs | int64 | count | Number of completed volume bars. |
| vpin_qc_pass | bool | qc_flag | QC flag for enough bars to compute VPIN. |
