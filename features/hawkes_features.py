"""Hawkes process self-excitation metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, MutableMapping, Sequence

import math

import numpy as np
import pandas as pd

__all__ = [
    "fit_exponential_hawkes",
    "hawkes_self_excitation_metrics",
]


_EPS = 1e-9


@dataclass(slots=True)
class HawkesFitResult:
    """Container for Hawkes parameter estimates."""

    baseline: float
    amplitude: float
    decay: float
    branching_ratio: float
    kernel_norm: float
    log_likelihood: float
    converged: bool


def _prepare_timestamps(
    timestamps: Sequence[float],
    start_time: float | None,
    end_time: float | None,
) -> tuple[np.ndarray, float, float]:
    """Validate and normalise timestamps within an observation window."""

    if not timestamps:
        raise ValueError("At least one timestamp is required to fit a Hawkes process.")

    values = np.asarray(list(timestamps), dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Timestamps must be finite real numbers.")

    values.sort()

    window_start = values[0] if start_time is None else float(start_time)
    window_end = values[-1] if end_time is None else float(end_time)

    if window_end <= window_start:
        window_end = values[-1] + 1e-6
        if window_end <= window_start:
            raise ValueError("Observation window must have a positive duration.")

    shifted = values - window_start
    total_duration = window_end - window_start
    if total_duration <= 0:
        raise ValueError("Observation window must have a positive duration.")

    return shifted, window_start, window_end


def _inter_event_summations(times: np.ndarray, decay: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute recursive sums used in Hawkes likelihood derivatives."""

    if decay <= 0:
        raise ValueError("Decay parameter must be strictly positive.")

    n_obs = times.shape[0]
    history_sums = np.zeros(n_obs)
    lag_weight_sums = np.zeros(n_obs)
    if n_obs <= 1:
        return history_sums, lag_weight_sums

    for idx in range(1, n_obs):
        dt = float(times[idx] - times[idx - 1])
        dt = max(dt, 0.0)
        exp_term = math.exp(-decay * dt)
        history_sums[idx] = exp_term * (history_sums[idx - 1] + 1.0)
        lag_weight_sums[idx] = exp_term * (lag_weight_sums[idx - 1] + dt * (history_sums[idx - 1] + 1.0))

    return history_sums, lag_weight_sums


def fit_exponential_hawkes(
    timestamps: Sequence[float],
    *,
    start_time: float | None = None,
    end_time: float | None = None,
    baseline_init: float | None = None,
    amplitude_init: float | None = None,
    decay_init: float | None = None,
    max_iter: int = 200,
    tol: float = 1e-6,
) -> HawkesFitResult:
    r"""Fit a univariate Hawkes process with an exponential kernel.

    The conditional intensity is parameterised as::

        \lambda(t) = \mu + \alpha \sum_{t_i < t} e^{-\beta (t - t_i)}

    where ``\mu`` is the baseline intensity, ``\alpha`` the excitation
    amplitude, and ``\beta`` the decay. The kernel norm and branching ratio
    are both given by ``\alpha / \beta``.

    Parameters
    ----------
    timestamps:
        Sorted or unsorted event timestamps.
    start_time, end_time:
        Optional observation window. When omitted the window is derived from
        the first and last timestamps.
    baseline_init, amplitude_init, decay_init:
        Optional initial guesses for the optimisation. When omitted sensible
        heuristics based on the observed event rate are used.
    max_iter:
        Maximum number of gradient-ascent iterations.
    tol:
        Termination tolerance expressed as the maximum absolute change in the
        log-parameter vector.

    Returns
    -------
    HawkesFitResult
        Estimated parameters and optimisation diagnostics.
    """

    if max_iter <= 0:
        raise ValueError("max_iter must be a positive integer.")
    if tol <= 0:
        raise ValueError("tol must be strictly positive.")

    shifted, window_start, window_end = _prepare_timestamps(timestamps, start_time, end_time)
    duration = window_end - window_start
    event_count = shifted.shape[0]

    if event_count < 2:
        baseline = max(float(event_count) / max(duration, _EPS), _EPS)
        return HawkesFitResult(
            baseline=baseline,
            amplitude=0.0,
            decay=1.0,
            branching_ratio=0.0,
            kernel_norm=0.0,
            log_likelihood=float("nan"),
            converged=False,
        )

    inter_arrival = np.diff(shifted)
    mean_gap = float(np.mean(inter_arrival)) if inter_arrival.size > 0 else float(duration) / max(event_count, 1)
    mean_gap = max(mean_gap, 1e-6)

    decay = float(decay_init) if decay_init is not None else 1.0 / mean_gap
    decay = max(decay, 1e-6)

    rate = float(event_count) / max(duration, _EPS)
    baseline = max(baseline_init if baseline_init is not None else 0.5 * rate, _EPS)
    amplitude = max(amplitude_init if amplitude_init is not None else 0.5 * decay, _EPS)

    # Ensure the initial branching ratio is strictly less than 1.
    branching_ratio = amplitude / decay
    if branching_ratio >= 0.95:
        amplitude = 0.95 * decay

    log_params = np.array([math.log(baseline), math.log(amplitude), math.log(decay)], dtype=float)

    def _log_likelihood(mu: float, alpha: float, beta: float) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
        history, lag_weights = _inter_event_summations(shifted, beta)
        lambda_values = mu + alpha * history
        if np.any(lambda_values <= _EPS):
            return float("-inf"), history, lag_weights, lambda_values

        tail_deltas = (window_end - window_start) - shifted
        tail_deltas = np.maximum(tail_deltas, 0.0)
        exp_tail = np.exp(-beta * tail_deltas)
        compensation = np.sum(1.0 - exp_tail)
        loglik = float(np.sum(np.log(lambda_values)))
        loglik -= mu * duration
        loglik -= (alpha / beta) * compensation
        return loglik, history, lag_weights, lambda_values

    current_loglik, hist_cache, lag_cache, lambda_cache = _log_likelihood(
        math.exp(log_params[0]), math.exp(log_params[1]), math.exp(log_params[2])
    )

    if not math.isfinite(current_loglik):
        # Fallback to a Poisson-like estimate when the initialisation is invalid.
        baseline = rate
        return HawkesFitResult(
            baseline=baseline,
            amplitude=0.0,
            decay=1.0,
            branching_ratio=0.0,
            kernel_norm=0.0,
            log_likelihood=float("nan"),
            converged=False,
        )

    converged = False
    step_scale = 0.01

    for _ in range(max_iter):
        mu = math.exp(log_params[0])
        alpha = math.exp(log_params[1])
        beta = math.exp(log_params[2])

        history = hist_cache
        lag_weights = lag_cache
        lambda_values = lambda_cache

        tail_deltas = (window_end - window_start) - shifted
        tail_deltas = np.maximum(tail_deltas, 0.0)
        exp_tail = np.exp(-beta * tail_deltas)
        compensation = np.sum(1.0 - exp_tail)
        tail_weight = np.sum(tail_deltas * exp_tail)

        inv_lambda = 1.0 / lambda_values
        grad_mu = float(np.sum(inv_lambda) - duration)
        grad_alpha = float(np.sum(history * inv_lambda) - (1.0 / beta) * compensation)
        grad_beta = float(
            -alpha * np.sum(lag_weights * inv_lambda)
            + (alpha / (beta**2)) * compensation
            - (alpha / beta) * tail_weight
        )

        grad_log = np.array([mu * grad_mu, alpha * grad_alpha, beta * grad_beta], dtype=float)
        update_norm = float(np.max(np.abs(step_scale * grad_log)))
        if update_norm < tol:
            converged = True
            break

        accepted = False
        step = step_scale
        for _ in range(12):
            candidate = log_params + step * grad_log
            mu_cand = math.exp(candidate[0])
            alpha_cand = math.exp(candidate[1])
            beta_cand = math.exp(candidate[2])

            if alpha_cand / beta_cand >= 0.995:
                alpha_cand = 0.995 * beta_cand
                candidate[1] = math.log(alpha_cand)

            cand_ll, hist_cache, lag_cache, lambda_cache = _log_likelihood(mu_cand, alpha_cand, beta_cand)
            if not math.isfinite(cand_ll) or cand_ll < current_loglik - 1e-9:
                step *= 0.5
                continue

            log_params = candidate
            current_loglik = cand_ll
            accepted = True
            break

        if not accepted:
            break

    baseline = math.exp(log_params[0])
    amplitude = math.exp(log_params[1])
    decay = math.exp(log_params[2])
    branching_ratio = amplitude / decay
    kernel_norm = branching_ratio

    return HawkesFitResult(
        baseline=baseline,
        amplitude=amplitude,
        decay=decay,
        branching_ratio=branching_ratio,
        kernel_norm=kernel_norm,
        log_likelihood=current_loglik,
        converged=converged,
    )


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def hawkes_self_excitation_metrics(
    events: pd.DataFrame,
    *,
    event_col: str = "event_type",
    time_col: str = "timestamp",
    group_cols: Sequence[str] = ("symbol", "date", "window"),
    start_col: str | None = None,
    end_col: str | None = None,
    decay_init: float | None = None,
    max_iter: int = 200,
    tol: float = 1e-6,
) -> pd.DataFrame:
    """Compute Hawkes self-excitation metrics per (symbol, date, window, event).

    Parameters
    ----------
    events:
        DataFrame containing event timestamps. The frame must include the
        grouping columns, the event type column, and the timestamp column.
    event_col:
        Column identifying the event stream (e.g. ``"orders"`` or ``"trades"``).
    time_col:
        Column containing monotonically increasing timestamps per group.
    group_cols:
        Columns defining independent observation windows.
    start_col, end_col:
        Optional columns specifying explicit observation window boundaries.
    decay_init:
        Optional initial decay shared across fits. When omitted a window-level
        heuristic is used.
    max_iter, tol:
        Passed through to :func:`fit_exponential_hawkes`.

    Returns
    -------
    pandas.DataFrame
        One row per (group, event type) with branching ratio and kernel norm
        alongside diagnostic fields.
    """

    required_columns: list[str] = list(group_cols) + [event_col, time_col]
    _require_columns(events, required_columns)
    if start_col is not None:
        _require_columns(events, [start_col])
    if end_col is not None:
        _require_columns(events, [end_col])

    if events.empty:
        columns: MutableMapping[str, object] = {
            **{col: pd.Series(dtype=events[col].dtype) for col in group_cols if col in events},
            event_col: pd.Series(dtype="object"),
            "branching_ratio": pd.Series(dtype="float64"),
            "kernel_norm": pd.Series(dtype="float64"),
            "baseline": pd.Series(dtype="float64"),
            "amplitude": pd.Series(dtype="float64"),
            "decay": pd.Series(dtype="float64"),
            "log_likelihood": pd.Series(dtype="float64"),
            "event_count": pd.Series(dtype="int64"),
            "duration": pd.Series(dtype="float64"),
            "converged": pd.Series(dtype="boolean"),
        }
        return pd.DataFrame(columns)

    events_sorted = events.sort_values(list(group_cols) + [event_col, time_col])
    rows: list[Mapping[str, object]] = []

    for key, group in events_sorted.groupby(list(group_cols), sort=False):
        window_start = float(group[start_col].iloc[0]) if start_col else float(group[time_col].min())
        window_end = float(group[end_col].iloc[0]) if end_col else float(group[time_col].max())
        window_end = max(window_end, window_start + 1e-6)
        duration = window_end - window_start

        for event_type, event_group in group.groupby(event_col, sort=False):
            timestamps = event_group[time_col].to_list()
            event_count = len(timestamps)
            if event_count == 0:
                continue

            try:
                fit = fit_exponential_hawkes(
                    timestamps,
                    start_time=window_start,
                    end_time=window_end,
                    decay_init=decay_init,
                    max_iter=max_iter,
                    tol=tol,
                )
            except ValueError:
                fit = HawkesFitResult(
                    baseline=float(event_count) / max(duration, _EPS),
                    amplitude=0.0,
                    decay=1.0,
                    branching_ratio=0.0,
                    kernel_norm=0.0,
                    log_likelihood=float("nan"),
                    converged=False,
                )

            result: dict[str, object] = {
                **{col: val for col, val in zip(group_cols, key)},
                event_col: event_type,
                "branching_ratio": fit.branching_ratio,
                "kernel_norm": fit.kernel_norm,
                "baseline": fit.baseline,
                "amplitude": fit.amplitude,
                "decay": fit.decay,
                "log_likelihood": fit.log_likelihood,
                "event_count": int(event_count),
                "duration": float(duration),
                "converged": bool(fit.converged),
            }
            rows.append(result)

    if not rows:
        raise ValueError("No events were processed for Hawkes fitting.")

    return pd.DataFrame(rows)
