"""Unit tests for VPIN computations."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from features.vpin import compute_vpin  # noqa: E402


@pytest.fixture()
def balanced_trades() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2024-01-02 09:30:00",
            "2024-01-02 09:30:10",
            "2024-01-02 09:30:20",
            "2024-01-02 09:30:30",
            "2024-01-02 09:30:40",
            "2024-01-02 09:30:50",
            "2024-01-02 09:31:00",
            "2024-01-02 09:31:10",
        ]
    )
    prices = [100.0, 99.5, 100.5, 100.0, 100.5, 100.0, 100.5, 100.0]
    sizes = [50] * len(prices)
    return pd.DataFrame(
        {
            "symbol": "AAPL",
            "date": "2024-01-02",
            "window": "pre",
            "timestamp": timestamps,
            "price": prices,
            "size": sizes,
        }
    )


@pytest.fixture()
def imbalanced_trades() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02 09:30:00", periods=8, freq="10s")
    prices = [100.0 + 0.1 * i for i in range(len(timestamps))]
    sizes = [50] * len(prices)
    return pd.DataFrame(
        {
            "symbol": "AAPL",
            "date": "2024-01-02",
            "window": "pre",
            "timestamp": timestamps,
            "price": prices,
            "size": sizes,
        }
    )


def test_vpin_balanced_flow_returns_low_values(balanced_trades: pd.DataFrame) -> None:
    result = compute_vpin(balanced_trades, bucket_volume=100, rolling_bars=2)
    assert result.shape == (1, 7)
    assert pytest.approx(result.loc[0, "vpin"], abs=1e-6) == 0.0
    assert pytest.approx(result.loc[0, "vpin_change"], abs=1e-6) == 0.0
    assert result.loc[0, "vpin_obs"] == 4
    assert bool(result.loc[0, "vpin_qc_pass"]) is True


def test_vpin_imbalanced_flow_elevates_vpin(imbalanced_trades: pd.DataFrame) -> None:
    result = compute_vpin(imbalanced_trades, bucket_volume=100, rolling_bars=2)
    assert result.shape == (1, 7)
    assert result.loc[0, "vpin"] > 0.9
    assert result.loc[0, "vpin_obs"] == 4
    assert bool(result.loc[0, "vpin_qc_pass"]) is True


def test_vpin_handles_empty_input() -> None:
    empty = pd.DataFrame(
        columns=["symbol", "date", "window", "timestamp", "price", "size"]
    )
    result = compute_vpin(empty, bucket_volume=100, rolling_bars=2)
    assert result.empty
