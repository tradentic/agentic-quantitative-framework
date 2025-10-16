"""Unit tests for Matrix Profile feature extraction."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("stumpy")

from features.matrix_profile import MatrixProfileFeatures, compute_matrix_profile_metrics


def _znorm(values: np.ndarray) -> np.ndarray:
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0.0:
        return np.zeros_like(values)
    return (values - mean) / std


def _znorm_euclidean_distance(subseq_a: np.ndarray, subseq_b: np.ndarray) -> float:
    return float(np.linalg.norm(_znorm(subseq_a) - _znorm(subseq_b)))


def _naive_matrix_profile(series: Iterable[float], subseq_length: int) -> np.ndarray:
    values = np.asarray(list(series), dtype=float)
    subsequences = values.shape[0] - subseq_length + 1
    exclusion_zone = max(1, int(np.ceil(subseq_length / 4)))
    profile = np.full(subsequences, np.inf)

    for idx in range(subsequences):
        window = values[idx : idx + subseq_length]
        for candidate in range(subsequences):
            if abs(candidate - idx) <= exclusion_zone:
                continue
            candidate_window = values[candidate : candidate + subseq_length]
            distance = _znorm_euclidean_distance(window, candidate_window)
            if distance < profile[idx]:
                profile[idx] = distance

    return profile


def _naive_motif_counts(series: Iterable[float], subseq_length: int, max_motifs: int) -> List[int]:
    values = np.asarray(list(series), dtype=float)
    profile = _naive_matrix_profile(values, subseq_length)
    subsequences = profile.shape[0]
    sorted_candidates = np.argsort(profile)
    used = np.zeros(subsequences, dtype=bool)
    counts: List[int] = []

    for idx in sorted_candidates:
        if len(counts) >= max_motifs:
            break
        if used[idx] or not np.isfinite(profile[idx]):
            continue

        seed = values[idx : idx + subseq_length]
        radius = profile[idx]
        tolerance = max(radius * 1e-6, 1e-9)
        effective_radius = max(radius, 0.0) + tolerance
        exclusion_zone = max(1, int(np.ceil(subseq_length / 4)))

        members = [idx]
        for candidate in range(subsequences):
            if candidate == idx or used[candidate]:
                continue
            if abs(candidate - idx) <= exclusion_zone:
                continue
            candidate_window = values[candidate : candidate + subseq_length]
            distance = _znorm_euclidean_distance(seed, candidate_window)
            if distance <= effective_radius:
                members.append(candidate)

        if len(members) <= 1:
            continue

        counts.append(len(members))
        used[members] = True

    return counts


def test_matrix_profile_metrics_match_naive() -> None:
    rng = np.random.default_rng(23)
    series = rng.normal(loc=0.0, scale=1.0, size=64)
    subseq_length = 8
    max_motifs = 3

    metrics = compute_matrix_profile_metrics(series, subseq_length, max_motifs)
    naive_profile = _naive_matrix_profile(series, subseq_length)

    assert isinstance(metrics, MatrixProfileFeatures)
    np.testing.assert_allclose(
        metrics.primary_motif_distance,
        np.nanmin(naive_profile),
        rtol=1e-5,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        metrics.discord_distance,
        np.nanmax(naive_profile),
        rtol=1e-5,
        atol=1e-5,
    )

    naive_counts = _naive_motif_counts(series, subseq_length, max_motifs)
    assert metrics.motif_counts == naive_counts


def test_matrix_profile_motifs_detect_repeated_patterns() -> None:
    series = np.array([1, 2, 1, 2, 1, 2, 3, 4, 3, 4], dtype=float)
    subseq_length = 2

    metrics = compute_matrix_profile_metrics(series, subseq_length, max_motifs=2)

    assert metrics.primary_motif_distance == pytest.approx(0.0, abs=1e-8)
    # first motif captures the repeated (1, 2) pattern, second motif captures (3, 4)
    assert metrics.motif_counts == [3, 2]


def test_matrix_profile_parameter_validation() -> None:
    with pytest.raises(ValueError):
        compute_matrix_profile_metrics([1.0, 2.0, 3.0], subseq_length=1)

    with pytest.raises(ValueError):
        compute_matrix_profile_metrics([1.0, 2.0], subseq_length=2)

    with pytest.raises(ValueError):
        compute_matrix_profile_metrics([1.0, 2.0, 3.0], subseq_length=2, max_motifs=0)
