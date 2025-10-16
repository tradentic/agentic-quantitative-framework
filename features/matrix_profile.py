"""Matrix Profile utilities for shape-based anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np


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

    Returns
    -------
    MatrixProfileFeatures
        Shape-anomaly metrics including discord distance, best motif distance, and motif counts.

    Raises
    ------
    ValueError
        If the series length or parameters are invalid.
    ImportError
        If ``stumpy`` is not installed.
    """

    _validate_parameters(series, subseq_length, max_motifs)
    values = _as_float_array(series)

    try:
        import stumpy  # type: ignore import-not-found
    except ImportError as exc:  # pragma: no cover - exercised when dependency missing
        raise ImportError(
            "stumpy is required to compute matrix profile features. Install it via 'pip install stumpy'."
        ) from exc

    profile = stumpy.stump(values, subseq_length)
    matrix_profile = profile[:, 0]

    discord_distance = _finite_nan_safe_max(matrix_profile)
    primary_motif_distance = _finite_nan_safe_min(matrix_profile)
    motif_counts = _compute_motif_counts(values, subseq_length, matrix_profile, max_motifs)

    return MatrixProfileFeatures(
        discord_distance=float(discord_distance) if np.isfinite(discord_distance) else float("nan"),
        primary_motif_distance=
        float(primary_motif_distance) if np.isfinite(primary_motif_distance) else float("nan"),
        motif_counts=motif_counts,
    )


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
