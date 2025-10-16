"""Matrix Profile utilities for shape-based anomaly detection.

The behaviour of :func:`compute_matrix_profile_metrics` can be tuned via the
``MATRIX_PROFILE_ENGINE`` environment variable. Supported values are

``"numba"`` (default)
    Uses :mod:`stumpy`'s accelerated implementation when available.

``"naive"``
    Forces the pure-Python fallback that avoids :mod:`stumpy` and NumPy's Numba
    extensions. This mode is slower but safer on platforms where compiling
    Numba-accelerated code is problematic.
"""

from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MatrixProfileFeatures:
    """Shape-anomaly metrics derived from a univariate Matrix Profile.

    Attributes
    ----------
    discord_distance:
        Distance between the most anomalous subsequence (discord) and its nearest neighbor.
    primary_motif_distance:
        Distance associated with the best motif (i.e. the smallest Matrix Profile value).
    motif_counts:
        Cardinality of the top ``k`` motif groups discovered in the series. Each entry
        represents how many windows participate in the motif, including the seed window.
    """

    discord_distance: float
    primary_motif_distance: float
    motif_counts: List[int]


def compute_matrix_profile_metrics(
    series: Sequence[float] | np.ndarray,
    subseq_length: int,
    max_motifs: int = 3,
    *,
    engine: str | None = None,
) -> MatrixProfileFeatures:
    """Compute discord and motif metrics for a univariate time series.

    Parameters
    ----------
    series:
        Iterable of numeric observations ordered in time.
    subseq_length:
        Sliding window length (``m``) used for the Matrix Profile subsequences.
    max_motifs:
        Maximum number of motif groups to report.
    engine:
        Optional engine selector. Accepts ``"numba"`` (uses :mod:`stumpy` when
        available) or ``"naive"`` for the pure Python fallback. When omitted the
        function consults the ``MATRIX_PROFILE_ENGINE`` environment variable and
        defaults to ``"numba"`` if unset.

    Returns
    -------
    MatrixProfileFeatures
        Shape-anomaly metrics including discord distance, best motif distance, and motif counts.

    Raises
    ------
    ValueError
        If the series length or parameters are invalid.
    """

    _validate_parameters(series, subseq_length, max_motifs)
    values = _as_float_array(series)

    requested_engine = _resolve_engine(engine)
    small_window = subseq_length < 3

    if small_window:
        actual_engine = "naive"
        logger.info(
            "Computing matrix profile with '%s' engine (forced for subseq_length < 3).",
            actual_engine,
        )
        matrix_profile = _naive_matrix_profile(values, subseq_length)
    elif requested_engine == "naive":
        actual_engine = "naive"
        logger.info("Computing matrix profile with '%s' engine.", actual_engine)
        matrix_profile = _naive_matrix_profile(values, subseq_length)
    else:
        actual_engine = "numba"
        try:
            import stumpy  # type: ignore import-not-found
        except ImportError:  # pragma: no cover - exercised when dependency missing
            message = (
                "stumpy is unavailable; falling back to the 'naive' matrix profile engine. "
                "Install 'stumpy' for accelerated execution."
            )
            logger.warning(message)
            warnings.warn(message, UserWarning, stacklevel=2)
            actual_engine = "naive"
            logger.info("Computing matrix profile with '%s' engine.", actual_engine)
            matrix_profile = _naive_matrix_profile(values, subseq_length)
        else:
            logger.info("Computing matrix profile with '%s' engine.", actual_engine)
            profile = stumpy.stump(values, subseq_length)
            matrix_profile = np.asarray(profile[:, 0], dtype=float)

    discord_distance = _finite_nan_safe_max(matrix_profile)
    primary_motif_distance = _finite_nan_safe_min(matrix_profile)
    if small_window:
        motif_counts = _small_window_motif_counts(values, subseq_length, max_motifs)
    else:
        motif_counts = _compute_motif_counts(values, subseq_length, matrix_profile, max_motifs)

    return MatrixProfileFeatures(
        discord_distance=float(discord_distance) if np.isfinite(discord_distance) else float("nan"),
        primary_motif_distance=
        float(primary_motif_distance) if np.isfinite(primary_motif_distance) else float("nan"),
        motif_counts=motif_counts,
    )


def _resolve_engine(engine: str | None) -> str:
    env_engine = os.getenv("MATRIX_PROFILE_ENGINE")
    candidate = (engine or env_engine or "numba").strip().lower()
    if candidate not in {"naive", "numba"}:
        logger.warning(
            "Unknown MATRIX_PROFILE_ENGINE value '%s'; defaulting to 'numba'.", candidate
        )
        return "numba"
    return candidate


def _validate_parameters(series: Sequence[float] | np.ndarray, subseq_length: int, max_motifs: int) -> None:
    if subseq_length <= 1:
        raise ValueError("subseq_length must be greater than 1")

    length = len(series)
    if length < subseq_length + 1:
        raise ValueError("series length must exceed subseq_length by at least one point")

    if max_motifs < 1:
        raise ValueError("max_motifs must be at least 1")


def _as_float_array(series: Sequence[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(list(series), dtype=float)
    if values.ndim != 1:
        raise ValueError("series must be one-dimensional")
    return values


def _naive_matrix_profile(series: np.ndarray, subseq_length: int) -> np.ndarray:
    subsequences = series.shape[0] - subseq_length + 1
    if subsequences <= 0:
        raise ValueError("series length must exceed subseq_length")
    profile = np.full(subsequences, float("inf"), dtype=float)
    if subsequences == 1:
        return profile

    for idx in range(subsequences):
        seed = series[idx : idx + subseq_length]
        best = float("inf")
        for candidate in range(subsequences):
            if candidate == idx:
                continue
            candidate_slice = series[candidate : candidate + subseq_length]
            distance = _znormalized_euclidean_distance(seed, candidate_slice)
            if distance < best:
                best = distance
        profile[idx] = best
    return profile


def _small_window_motif_counts(series: np.ndarray, subseq_length: int, max_motifs: int) -> List[int]:
    subsequences = series.shape[0] - subseq_length + 1
    if subsequences <= 0:
        return []
    pattern_counts: dict[tuple[float, ...], int] = {}
    for idx in range(subsequences):
        window = tuple(float(x) for x in series[idx : idx + subseq_length])
        pattern_counts[window] = pattern_counts.get(window, 0) + 1

    sorted_counts = sorted((count for count in pattern_counts.values() if count > 1), reverse=True)
    return sorted_counts[:max_motifs]


def _finite_nan_safe_max(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan")
    return float(np.max(finite))


def _finite_nan_safe_min(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan")
    return float(np.min(finite))


def _compute_motif_counts(
    series: np.ndarray,
    subseq_length: int,
    matrix_profile: np.ndarray,
    max_motifs: int,
) -> List[int]:
    profile_length = matrix_profile.shape[0]
    finite_mask = np.isfinite(matrix_profile)
    candidate_indices = np.flatnonzero(finite_mask)
    if candidate_indices.size == 0:
        return []

    sorted_candidates = candidate_indices[np.argsort(matrix_profile[candidate_indices])]
    used = np.zeros(profile_length, dtype=bool)
    counts: List[int] = []

    for idx in sorted_candidates:
        if len(counts) >= max_motifs:
            break
        if used[idx]:
            continue
        distance = matrix_profile[idx]
        if not np.isfinite(distance):
            continue

        members = _discover_motif_members(series, subseq_length, idx, distance, used)
        if len(members) <= 1:
            continue

        counts.append(len(members))
        used[members] = True

    return counts


def _discover_motif_members(
    series: np.ndarray,
    subseq_length: int,
    seed_index: int,
    radius: float,
    used: np.ndarray,
) -> np.ndarray:
    if not np.isfinite(radius):
        return np.array([], dtype=int)

    exclusion_zone = max(1, int(np.ceil(subseq_length / 4)))
    subsequences = series.shape[0] - subseq_length + 1
    seed = series[seed_index : seed_index + subseq_length]
    members = [seed_index]
    tolerance = max(radius * 1e-6, 1e-9)
    effective_radius = max(radius, 0.0) + tolerance

    for candidate in range(subsequences):
        if candidate == seed_index or used[candidate]:
            continue
        if abs(candidate - seed_index) <= exclusion_zone:
            continue
        candidate_subseq = series[candidate : candidate + subseq_length]
        distance = _znormalized_euclidean_distance(seed, candidate_subseq)
        if distance <= effective_radius:
            members.append(candidate)

    return np.array(sorted(set(members)), dtype=int)


def _znormalized_euclidean_distance(subseq_a: Iterable[float], subseq_b: Iterable[float]) -> float:
    a = np.asarray(subseq_a, dtype=float)
    b = np.asarray(subseq_b, dtype=float)

    a = _znorm(a)
    b = _znorm(b)
    return float(np.linalg.norm(a - b))


def _znorm(values: np.ndarray) -> np.ndarray:
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0.0:
        return np.zeros_like(values)
    return (values - mean) / std


__all__ = ["MatrixProfileFeatures", "compute_matrix_profile_metrics"]
