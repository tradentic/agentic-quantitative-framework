"""Utilities for detecting change-points in univariate time-series.

The module exposes a light-weight implementation of two popular detectors:

* An offline segmentation routine based on the PELT dynamic programming
  algorithm with an L2 cost (sum of squared errors) to detect level and
  volatility breaks.
* An optional Bayesian Online Change Point Detection (BOCPD) wrapper that
  produces run-length conditioned probabilities for streaming contexts.

The goal is to keep the public API minimal while still returning the key
artifacts required by downstream agents: break indices, level deltas, and a
per-step score vector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import math

import numpy as np


ArrayLike = Sequence[float] | np.ndarray


@dataclass
class ChangePointResult:
    """Container holding the outputs of a change-point detection run."""

    breakpoints: List[int]
    deltas: List[float]
    segment_means: List[float]
    score_series: np.ndarray
    bocpd_probabilities: Optional[np.ndarray] = None

    def as_dict(self) -> dict:
        """Return a serialisable dictionary representation."""

        return {
            "breakpoints": self.breakpoints,
            "deltas": self.deltas,
            "segment_means": self.segment_means,
            "score_series": self.score_series.tolist(),
            "bocpd_probabilities": None
            if self.bocpd_probabilities is None
            else self.bocpd_probabilities.tolist(),
        }


def change_point_scores(
    values: ArrayLike,
    penalty: float = 8.0,
    min_size: int = 10,
    max_breaks: Optional[int] = None,
    use_bocpd: bool = False,
    bocpd_hazard: float = 200.0,
    bocpd_max_run_length: Optional[int] = None,
) -> ChangePointResult:
    """Detect change-points and compute summary statistics.

    Parameters
    ----------
    values:
        Iterable of numeric observations.
    penalty:
        Penalty applied by the PELT objective. Higher values decrease the number of
        detected change-points.
    min_size:
        Minimum number of samples per segment.
    max_breaks:
        Optional cap on the number of breakpoints to return (largest deltas kept).
    use_bocpd:
        When ``True`` a Bayesian online detector is evaluated and its probability
        series included in the result.
    bocpd_hazard:
        Constant hazard parameter ``lambda`` used by BOCPD. Higher values favour
        shorter run lengths (more frequent changes).
    bocpd_max_run_length:
        Optional truncation for the run-length distribution used by BOCPD. Falling
        back to the length of ``values`` when not provided.

    Returns
    -------
    ChangePointResult
        Dataclass containing break indices, deltas between segment means, the
        individual segment means, and per-observation scores.
    """

    series = _to_numpy(values)
    if len(series) == 0:
        raise ValueError("`values` must contain at least one observation.")
    if min_size < 2:
        raise ValueError("`min_size` must be >= 2 to compute a segment mean.")

    breakpoints = _pelt(series, penalty=penalty, min_size=min_size)
    if max_breaks is not None and len(breakpoints) > max_breaks:
        breakpoints = _select_largest_deltas(series, breakpoints, max_breaks)

    segment_means = _segment_means(series, breakpoints)
    deltas = _segment_deltas(segment_means)
    score_series = _score_vector(len(series), breakpoints, deltas)

    bocpd_probs: Optional[np.ndarray] = None
    if use_bocpd:
        bocpd_probs = bocpd_probabilities(
            series,
            hazard=bocpd_hazard,
            max_run_length=bocpd_max_run_length,
        )

    return ChangePointResult(
        breakpoints=breakpoints,
        deltas=deltas,
        segment_means=segment_means,
        score_series=score_series,
        bocpd_probabilities=bocpd_probs,
    )


def _to_numpy(values: ArrayLike) -> np.ndarray:
    if isinstance(values, np.ndarray):
        series = values.astype(float, copy=False)
    else:
        series = np.asarray(list(values), dtype=float)
    if series.ndim != 1:
        raise ValueError("`values` must be one-dimensional.")
    return series


def _pelt(series: np.ndarray, penalty: float, min_size: int) -> List[int]:
    """Return change-point indices using a quadratic-time PELT solver."""

    n = len(series)
    if n < 2 * min_size:
        return []

    cumsum = np.zeros(n + 1)
    cumsumsq = np.zeros(n + 1)
    cumsum[1:] = np.cumsum(series)
    cumsumsq[1:] = np.cumsum(series**2)

    def segment_cost(start: int, end: int) -> float:
        length = end - start
        seg_sum = cumsum[end] - cumsum[start]
        seg_sumsq = cumsumsq[end] - cumsumsq[start]
        mean = seg_sum / length
        return seg_sumsq - 2 * mean * seg_sum + length * mean**2

    best_cost = np.full(n + 1, np.inf)
    best_cost[0] = -penalty
    prev = np.zeros(n + 1, dtype=int)

    for end in range(min_size, n + 1):
        candidates: List[Tuple[float, int]] = []
        for start in range(0, end - min_size + 1):
            if end - start < min_size:
                continue
            cost = best_cost[start] + segment_cost(start, end) + penalty
            candidates.append((cost, start))
        if not candidates:
            continue
        best_cost[end], prev[end] = min(candidates, key=lambda pair: pair[0])

    # Backtrack from the best final point.
    change_points: List[int] = []
    idx = n
    while idx > 0:
        start = prev[idx]
        if start == 0 and best_cost[idx] == np.inf:
            break
        if start == 0 and idx < n and idx < min_size:
            break
        if start == idx:
            break
        if idx != n:
            change_points.append(idx)
        idx = start

    change_points.sort()
    return change_points


def _segment_means(series: np.ndarray, breakpoints: Sequence[int]) -> List[float]:
    indices = [0, *breakpoints, len(series)]
    means: List[float] = []
    for start, end in zip(indices[:-1], indices[1:]):
        segment = series[start:end]
        means.append(float(segment.mean()))
    return means


def _segment_deltas(segment_means: Sequence[float]) -> List[float]:
    return [float(segment_means[i + 1] - segment_means[i]) for i in range(len(segment_means) - 1)]


def _score_vector(length: int, breakpoints: Sequence[int], deltas: Sequence[float]) -> np.ndarray:
    scores = np.zeros(length)
    for index, delta in zip(breakpoints, deltas):
        if 0 <= index < length:
            scores[index] = float(abs(delta))
    return scores


def _select_largest_deltas(
    series: np.ndarray, breakpoints: Sequence[int], max_breaks: int
) -> List[int]:
    if max_breaks <= 0:
        return []
    segment_means = _segment_means(series, breakpoints)
    deltas = _segment_deltas(segment_means)
    indexed = list(zip(breakpoints, map(abs, deltas)))
    indexed.sort(key=lambda item: item[1], reverse=True)
    selected_indices = {bp for bp, _ in indexed[:max_breaks]}
    return sorted(selected_indices)


def bocpd_probabilities(
    series: ArrayLike,
    hazard: float = 200.0,
    max_run_length: Optional[int] = None,
    prior_mean: float = 0.0,
    prior_kappa: float = 0.1,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
) -> np.ndarray:
    """Compute BOCPD change probabilities for a univariate series.

    The implementation follows the recursive message passing introduced by
    Adams & MacKay (2007) with a conjugate Gaussian model for unknown mean and
    variance.
    """

    x = _to_numpy(series)
    n = len(x)
    if n == 0:
        raise ValueError("`series` must not be empty.")
    if hazard <= 0:
        raise ValueError("`hazard` must be positive.")

    hazard_prob = 1.0 / hazard
    if not 0.0 < hazard_prob < 1.0:
        raise ValueError("`hazard` must be greater than 1.0 to produce a valid probability.")

    truncation = n if max_run_length is None else int(max_run_length)
    truncation = max(1, min(truncation, n))

    log_run_probs = np.full((n + 1, truncation + 1), -np.inf)
    log_run_probs[0, 0] = 0.0

    mu_t = np.full(truncation + 1, prior_mean)
    kappa_t = np.full(truncation + 1, prior_kappa)
    alpha_t = np.full(truncation + 1, prior_alpha)
    beta_t = np.full(truncation + 1, prior_beta)

    change_probs = np.zeros(n)

    log_hazard = math.log(hazard_prob)
    log_one_minus_hazard = math.log1p(-hazard_prob)

    for t in range(1, n + 1):
        value = x[t - 1]
        limit = min(t, truncation)
        predictive_log_probs = np.full(limit, -np.inf)

        for r in range(limit):
            mean = mu_t[r]
            kappa = kappa_t[r]
            alpha = alpha_t[r]
            beta = beta_t[r]
            scale = math.sqrt((beta * (kappa + 1)) / (alpha * kappa))
            dof = 2 * alpha
            predictive_log_probs[r] = _student_t_log_pdf(value - mean, dof, scale)

        for r in range(limit):
            log_growth = log_run_probs[t - 1, r] + predictive_log_probs[r] + log_one_minus_hazard
            log_run_probs[t, r + 1] = _logsumexp(log_run_probs[t, r + 1], log_growth)

        log_cp = _logsumexp_array(
            log_run_probs[t - 1, :limit] + predictive_log_probs[:limit] + log_hazard
        )
        change_probs[t - 1] = math.exp(log_cp)
        log_run_probs[t, 0] = log_cp

        current_slice = log_run_probs[t, : limit + 1]
        normaliser = _logsumexp_array(current_slice)
        log_run_probs[t, : limit + 1] -= normaliser

        mu_new = np.full(truncation + 1, prior_mean)
        kappa_new = np.full(truncation + 1, prior_kappa)
        alpha_new = np.full(truncation + 1, prior_alpha)
        beta_new = np.full(truncation + 1, prior_beta)

        for r in range(limit):
            kappa_new[r + 1] = kappa_t[r] + 1.0
            mu_new[r + 1] = (kappa_t[r] * mu_t[r] + value) / kappa_new[r + 1]
            alpha_new[r + 1] = alpha_t[r] + 0.5
            diff = value - mu_t[r]
            beta_new[r + 1] = beta_t[r] + (kappa_t[r] * diff**2) / (2 * (kappa_t[r] + 1))

        mu_t = mu_new
        kappa_t = kappa_new
        alpha_t = alpha_new
        beta_t = beta_new

    return change_probs


def _student_t_log_pdf(x: float, dof: float, scale: float) -> float:
    coef = math.lgamma((dof + 1) / 2) - math.lgamma(dof / 2)
    coef -= 0.5 * math.log(dof * math.pi)
    coef -= math.log(scale)
    inner = 1 + (x / scale) ** 2 / dof
    return coef - ((dof + 1) / 2) * math.log(inner)


def _logsumexp(a: float, b: float) -> float:
    if a == -np.inf:
        return b
    if b == -np.inf:
        return a
    if a > b:
        return a + math.log1p(math.exp(b - a))
    return b + math.log1p(math.exp(a - b))


def _logsumexp_array(arr: np.ndarray) -> float:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return -np.inf
    m = float(finite.max())
    return m + math.log(np.sum(np.exp(finite - m)))

