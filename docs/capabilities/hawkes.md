# Hawkes Self-Excitation Capability

## Motivation
- Quantify reflexivity in order-driven markets by estimating Hawkes self-excitation on orders, cancels, and trades.
- Surface branching ratios and kernel norms to monitor cascade risk across venues and assets.
- Provide a lightweight, dependency-free estimator so research agents can analyse Hawkes dynamics without `tick` binaries.

## Inputs
- Event DataFrame with columns: `symbol`, `date`, `window`, `event_type`, `timestamp` (float seconds or pandas timestamps).
- Optional observation bounds per window via `start_col` / `end_col` if trading sessions differ from observed timestamps.
- Optional manual initialisation for decay (`decay_init`), maximum iterations, and tolerance for the gradient solver.

## Outputs
- Branching ratio (`branching_ratio`) and kernel norm (`kernel_norm`) per `(symbol, date, window, event_type)`.
- Baseline intensity (`baseline`), excitation amplitude (`amplitude`), exponential decay (`decay`), log-likelihood, event counts, duration, and convergence flag.
- Helper `fit_exponential_hawkes` returns a `HawkesFitResult` dataclass for ad-hoc fits outside grouped windows.

## Configuration & Usage Notes
- Ensure timestamps are numeric floats (seconds) or convert pandas `Timestamp` to `.view(float)`/`.astype(float)` before fitting.
- Keep branching ratios below 1.0 by vetting decay initialisations; the fitter clamps proposals to 0.995 to preserve stationarity.
- For sparse windows (<2 events) the estimator falls back to a Poisson baseline with zero excitation.
- Control solver aggressiveness via `max_iter` and `tol`; a smaller tolerance tightens convergence checks at extra runtime cost.

## CLI Examples
- Run Hawkes feature tests: `python -m pytest tests/features/test_hawkes.py`.
- Estimate branching ratios on a CSV of event logs:
  ```bash
  python - <<'PY'
  import pandas as pd
  from features.hawkes_features import hawkes_self_excitation_metrics

  events = pd.read_csv('events.csv')
  metrics = hawkes_self_excitation_metrics(events)
  print(metrics.head())
  PY
  ```

## Failure Modes & Retries
- Missing required columns raise `ValueError` before optimisation to keep data issues explicit.
- Empty DataFrames produce an empty, typed metrics frame; callers should check `.empty` before downstream joins.
- If gradients cannot improve the likelihood within 12 backtracking steps the solver exits early with `converged=False`.
- Non-positive decay seeds or degenerate observation windows trigger a fallback Poisson estimate with zero excitation.

## Validation Checks
- Synthetic Hawkes simulations in `tests/features/test_hawkes.py` assert positive branching ratios and column coverage.
- Spot-check kernel norms against branching ratios—they match by construction for exponential kernels.
- Monitor convergence flags; persistent `False` values suggest reconsidering initialisation or event window definitions.
