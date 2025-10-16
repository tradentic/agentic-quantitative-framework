# Matrix Profile Shape Features

## Motivation
- Detect subsequence shape anomalies (discords) and repeated structures (motifs) in liquidity features such as volume, bid-ask spread, or off-exchange share.
- Provide distance-based diagnostics that complement volatility or returns-driven indicators.

## Inputs & Outputs
- **Inputs:**
  - Univariate numeric time series ordered in time.
  - Subsequence length ``m`` that defines the sliding window size.
  - Maximum motif groups ``k`` to enumerate.
- **Outputs:**
  - Discord distance for the most anomalous window.
  - Primary motif distance (minimum Matrix Profile value).
  - Motif participation counts for the top ``k`` motifs.

## Configuration
- `subseq_length` (int): window size used when computing the Matrix Profile; must be greater than one and smaller than the series length.
- `max_motifs` (int): number of motif groups to return; defaults to three.
- `MATRIX_PROFILE_ENGINE` (env): set to `naive` to force the pure-Python implementation when compiling `stumpy`/Numba kernels is unsafe for the target environment. Defaults to `numba` which attempts to use `stumpy`.
- `stumpy` version >= 1.11 recommended for performant Matrix Profile computation.

## CLI Example
```bash
python - <<'PY'
from features.matrix_profile import compute_matrix_profile_metrics
import numpy as np

series = np.loadtxt('data/off_exchange_share.csv', delimiter=',')
metrics = compute_matrix_profile_metrics(series, subseq_length=24, max_motifs=3)
print(metrics)
PY
```

## Failure Modes
- Automatic fallback to the naive engine when `stumpy` import fails. A warning is logged/emitted so operators are aware that accelerated execution is unavailable.
- ``ValueError`` if the series is shorter than ``subseq_length + 1`` or if parameters are out of bounds.
- Degenerate (flat) subsequences yield zero variance; the implementation falls back to zero vectors to keep motif distances finite.

## Validation Checks
- Unit tests compare discord and motif distances against a naive Matrix Profile implementation on seeded synthetic data.
- Repeated-pattern fixtures ensure motif counts align with expected cluster cardinalities.
- Parameter validation tests enforce guard rails around subsequence length and motif settings.
