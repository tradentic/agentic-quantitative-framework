# Change-Point Scores

## Motivation

- Detect structural breaks in price levels or realised volatility to trigger
  downstream regime-aware models.
- Surface interpretable break magnitudes that can be consumed by feature
  ranking or alerting pipelines.

## Inputs / Outputs

- **Inputs:** univariate numeric series (Python sequences, ``numpy`` arrays).
- **Outputs:**
  - Breakpoint indices from the PELT L2 cost objective.
  - Level deltas between adjacent segments and per-step score vectors.
  - Optional BOCPD probability trace for online monitoring.

## Configs

- ``penalty``: controls sparsity of detected breaks.
- ``min_size``: minimum samples per segment in the offline solver.
- ``max_breaks``: optional cap keeping the largest deltas.
- ``use_bocpd`` & ``bocpd_hazard``: toggle and configure Bayesian online
  detection.
- ``bocpd_max_run_length``: truncate run-length distribution for speed.

## CLI Example

```bash
python -c "from features.change_points import change_point_scores; \
import numpy as np; series = np.r_[np.zeros(50), np.ones(50) * 2]; \
print(change_point_scores(series, penalty=8.0).as_dict())"
```

## Failure Modes

- Very short series (fewer than two segments) return no breakpoints.
- Heavy-tailed noise can inflate BOCPD false positives; tune the hazard and
  prior scale parameters.
- Strongly autocorrelated series may require domain-specific cost functions,
  which are not covered by this minimal implementation.

## Validation Checks

- Synthetic step changes (unit tests) must recover the planted breaks within
  ±5 observations.
- BOCPD probabilities should peak around the same locations as offline
  breakpoints on the synthetic benchmarks.
- Review delta magnitudes to ensure they align with expected jump sizes.
