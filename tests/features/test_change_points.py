"""Unit tests for the change-point utilities."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[2]))

from features.change_points import ChangePointResult, bocpd_probabilities, change_point_scores


def synthetic_series() -> np.ndarray:
    rng = np.random.default_rng(seed=42)
    baseline = np.full(60, 0.0)
    jump_one = np.full(40, 2.0)
    jump_two = np.full(50, -1.0)
    base = np.concatenate([baseline, jump_one, jump_two])
    noise = rng.normal(scale=0.2, size=base.shape[0])
    return base + noise


def test_change_point_scores_detects_step_changes() -> None:
    series = synthetic_series()
    result = change_point_scores(series, penalty=10.0, min_size=20)

    assert isinstance(result, ChangePointResult)
    assert result.breakpoints, "Expected at least one breakpoint"

    # The synthetic series contains jumps around indices 60 and 100.
    assert any(abs(bp - 60) <= 5 for bp in result.breakpoints)
    assert any(abs(bp - 100) <= 5 for bp in result.breakpoints)

    # Deltas should reflect step differences in the mean.
    assert len(result.deltas) == len(result.breakpoints)
    assert any(delta > 1.0 for delta in result.deltas)

    # Score vector should have non-zero entries at breakpoint indices.
    for idx in result.breakpoints:
        assert result.score_series[idx] > 0


def test_bocpd_high_probability_near_change() -> None:
    series = synthetic_series()
    probabilities = bocpd_probabilities(series, hazard=30.0, max_run_length=80)

    assert probabilities.shape == (len(series),)
    top_indices = np.argsort(probabilities)[-20:]
    assert any(abs(idx - 60) <= 7 for idx in top_indices)
    assert any(abs(idx - 100) <= 10 for idx in top_indices)


def test_change_point_scores_with_bocpd_flag() -> None:
    series = synthetic_series()
    result = change_point_scores(series, penalty=9.0, min_size=15, use_bocpd=True, bocpd_hazard=60.0)

    assert result.bocpd_probabilities is not None
    assert result.bocpd_probabilities.shape == (len(series),)
