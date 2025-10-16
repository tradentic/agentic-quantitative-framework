"""Unit tests for microstructure feature computations."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure repository root is importable when pytest prepends the tests directory to sys.path.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from features.microstructure import (  # noqa: E402
    amihud_illiq,
    book_imbalance,
    compute_ofi,
    kyle_lambda,
    spreads,
)


@pytest.fixture()
def sample_quotes() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2024-01-02 09:30:00",
            "2024-01-02 09:30:30",
            "2024-01-02 09:31:00",
            "2024-01-02 09:31:30",
        ]
    )
    return pd.DataFrame(
        {
            "symbol": "AAPL",
            "date": "2024-01-02",
            "window": "w1",
            "timestamp": timestamps,
            "bid_price": [100.00, 100.10, 100.10, 100.00],
            "bid_size": [10, 12, 11, 9],
            "ask_price": [100.50, 100.60, 100.55, 100.50],
            "ask_size": [8, 8, 7, 7],
        }
    )


@pytest.fixture()
def sample_trades() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2024-01-02 09:30:10",
            "2024-01-02 09:30:40",
            "2024-01-02 09:31:10",
        ]
    )
    return pd.DataFrame(
        {
            "symbol": "AAPL",
            "date": "2024-01-02",
            "window": "w1",
            "timestamp": timestamps,
            "price": [100.12, 100.18, 100.14],
            "size": [50, 80, 60],
        }
    )


def test_compute_ofi(sample_quotes: pd.DataFrame) -> None:
    result = compute_ofi(sample_quotes)
    assert result.shape == (1, 6)
    ofi_value = result.loc[0, "ofi"]
    assert pytest.approx(ofi_value, rel=1e-6) == -6.0
    assert result.loc[0, "ofi_obs"] == 4
    assert bool(result.loc[0, "ofi_qc_pass"]) is True


def test_book_imbalance(sample_quotes: pd.DataFrame) -> None:
    result = book_imbalance(sample_quotes)
    assert result.shape == (1, 6)
    imbalance = result.loc[0, "book_imbalance"]
    assert pytest.approx(imbalance, rel=1e-6) == 0.125
    assert result.loc[0, "book_imbalance_obs"] == 4
    assert bool(result.loc[0, "book_imbalance_qc_pass"]) is True


def test_kyle_lambda(sample_trades: pd.DataFrame, sample_quotes: pd.DataFrame) -> None:
    result = kyle_lambda(sample_trades, sample_quotes)
    assert result.shape == (1, 6)
    expected = (0.06 / 80 + 0.04 / 60) / 2
    assert pytest.approx(result.loc[0, "kyle_lambda"], rel=1e-6) == expected
    assert result.loc[0, "kyle_lambda_obs"] == 2
    assert bool(result.loc[0, "kyle_lambda_qc_pass"]) is True


def test_amihud_illiq(sample_trades: pd.DataFrame) -> None:
    result = amihud_illiq(sample_trades)
    assert result.shape == (1, 6)
    returns = sample_trades["price"].pct_change().abs()
    dollar_volume = sample_trades["price"] * sample_trades["size"]
    expected = ((returns / dollar_volume).dropna()).mean()
    assert pytest.approx(result.loc[0, "amihud_illiq"], rel=1e-9) == expected
    assert result.loc[0, "amihud_obs"] == 2
    assert bool(result.loc[0, "amihud_qc_pass"]) is True


def test_spreads(sample_quotes: pd.DataFrame) -> None:
    result = spreads(sample_quotes)
    assert result.shape == (1, 7)
    spread = sample_quotes["ask_price"] - sample_quotes["bid_price"]
    mid = (sample_quotes["ask_price"] + sample_quotes["bid_price"]) / 2
    mask = (spread >= 0) & (mid > 0)
    expected_abs = spread[mask].mean()
    expected_rel = (spread / mid)[mask].mean()
    assert pytest.approx(result.loc[0, "avg_spread"], rel=1e-6) == expected_abs
    assert pytest.approx(result.loc[0, "avg_rel_spread"], rel=1e-6) == expected_rel
    assert result.loc[0, "spreads_obs"] == int(mask.sum())
    assert bool(result.loc[0, "spreads_qc_pass"]) is True


def test_empty_inputs_return_empty_frames() -> None:
    empty_quotes = pd.DataFrame(
        columns=["symbol", "date", "window", "timestamp", "bid_price", "bid_size", "ask_price", "ask_size"]
    )
    empty_trades = pd.DataFrame(
        columns=["symbol", "date", "window", "timestamp", "price", "size"]
    )

    assert compute_ofi(empty_quotes).empty
    assert book_imbalance(empty_quotes).empty
    assert kyle_lambda(empty_trades, empty_quotes).empty
    assert amihud_illiq(empty_trades).empty
    assert spreads(empty_quotes).empty
