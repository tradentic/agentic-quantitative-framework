"""Unit tests for Hawkes self-excitation metrics."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure repository root is on sys.path for direct feature imports during pytest.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from features.hawkes_features import (  # noqa: E402
    fit_exponential_hawkes,
    hawkes_self_excitation_metrics,
)


def _simulate_hawkes(
    *,
    baseline: float,
    amplitude: float,
    decay: float,
    horizon: float,
    seed: int,
) -> list[float]:
    """Simulate a Hawkes process via Ogata's thinning algorithm."""

    rng = np.random.default_rng(seed)
    timestamps: list[float] = []
    upper_intensity = baseline
    current_time = 0.0

    while True:
        u = rng.random()
        if u <= 0:
            continue
        wait = -math.log(u) / max(upper_intensity, baseline)
        current_time += wait
        if current_time >= horizon:
            break

        if timestamps:
            lags = np.array(current_time) - np.array(timestamps)
            intensity = baseline + amplitude * np.exp(-decay * lags).sum()
        else:
            intensity = baseline

        if intensity <= 0:
            upper_intensity = baseline
            continue

        accept_prob = intensity / max(upper_intensity, intensity)
        if rng.random() <= accept_prob:
            timestamps.append(current_time)
            upper_intensity = intensity + amplitude
        else:
            upper_intensity = intensity

        upper_intensity = max(upper_intensity, baseline)

    return timestamps


def test_fit_exponential_hawkes_recovers_branching_ratio() -> None:
    baseline = 0.3
    amplitude = 0.45
    decay = 1.5
    branching_true = amplitude / decay

    timestamps = _simulate_hawkes(
        baseline=baseline,
        amplitude=amplitude,
        decay=decay,
        horizon=400.0,
        seed=42,
    )

    result = fit_exponential_hawkes(timestamps)

    assert 0.0 < result.branching_ratio < 0.95
    assert math.isfinite(result.log_likelihood)
    assert math.isclose(result.branching_ratio, branching_true, rel_tol=0.5)


def test_hawkes_metrics_dataframe_returns_expected_columns() -> None:
    baseline = 0.25
    amplitude = 0.35
    decay = 1.2

    rows: list[dict[str, object]] = []
    for idx, event_type in enumerate(["orders", "cancels", "trades"]):
        timestamps = _simulate_hawkes(
            baseline=baseline,
            amplitude=amplitude,
            decay=decay,
            horizon=300.0,
            seed=idx + 100,
        )
        for ts in timestamps:
            rows.append(
                {
                    "symbol": "XYZ",
                    "date": "2024-01-01",
                    "window": "session",
                    "event_type": event_type,
                    "timestamp": ts,
                }
            )

    events = pd.DataFrame(rows)

    metrics = hawkes_self_excitation_metrics(events)

    assert set(metrics.columns) == {
        "symbol",
        "date",
        "window",
        "event_type",
        "branching_ratio",
        "kernel_norm",
        "baseline",
        "amplitude",
        "decay",
        "log_likelihood",
        "event_count",
        "duration",
        "converged",
    }

    assert (metrics["branching_ratio"] > 0).all()
    assert (metrics["kernel_norm"] > 0).all()
