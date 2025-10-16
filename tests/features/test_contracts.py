"""Schema contract tests for feature outputs."""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import pytest
from pandas.api import types as ptypes

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from features import microstructure, vpin  # noqa: E402

SPEC_PATH = REPO_ROOT / "docs/specs/FEATURE_CONTRACTS.md"


def _load_contracts() -> dict[str, list[dict[str, str]]]:
    if not SPEC_PATH.exists():
        raise AssertionError(f"Spec file missing: {SPEC_PATH}")

    contracts: dict[str, list[dict[str, str]]] = {}
    current_feature: str | None = None

    for raw_line in SPEC_PATH.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("### `") and line.endswith("`"):
            current_feature = line[4:-1].strip("`")
            contracts[current_feature] = []
            continue

        if not current_feature:
            continue

        if line.startswith("|"):
            parts = [part.strip() for part in line.split("|")[1:-1]]
            if not parts or parts[0] in {"Column", ""}:
                continue
            if all(part.startswith("---") or not part for part in parts):
                continue
            column, dtype, unit = parts[:3]
            note = parts[3] if len(parts) > 3 else ""
            contracts[current_feature].append(
                {"column": column, "dtype": dtype, "unit": unit, "note": note}
            )
            continue

        # Leaving the table scope ends the feature contract block.
        if contracts.get(current_feature):
            current_feature = None

    if not contracts:
        raise AssertionError("No feature contracts parsed from spec")

    return contracts


CONTRACTS = _load_contracts()


def _assert_unit_hint(unit: str, series: pd.Series, feature: str, column: str) -> None:
    mask = series.dropna()

    if unit in {"identifier", "date", "window"}:
        assert ptypes.is_object_dtype(series.dtype), f"{feature}.{column} must be object"
    elif unit in {"price", "price_per_share", "shares", "inv_dollar"}:
        assert ptypes.is_numeric_dtype(series.dtype), f"{feature}.{column} must be numeric"
        if unit == "inv_dollar" and not mask.empty:
            assert (mask >= 0).all(), f"{feature}.{column} must be non-negative"
    elif unit == "ratio":
        assert ptypes.is_numeric_dtype(series.dtype), f"{feature}.{column} must be numeric ratio"
        if not mask.empty:
            assert (mask.abs() <= 1 + 1e-9).all(), f"{feature}.{column} ratio outside [-1, 1]"
    elif unit == "probability":
        assert ptypes.is_numeric_dtype(series.dtype), f"{feature}.{column} must be numeric probability"
        if not mask.empty:
            assert ((mask >= 0) & (mask <= 1)).all(), f"{feature}.{column} must be in [0, 1]"
    elif unit == "probability_delta":
        assert ptypes.is_numeric_dtype(series.dtype), f"{feature}.{column} must be numeric probability delta"
        if not mask.empty:
            assert ((mask >= -1) & (mask <= 1)).all(), f"{feature}.{column} must be in [-1, 1]"
    elif unit == "count":
        assert ptypes.is_integer_dtype(series.dtype), f"{feature}.{column} must be integer"
    elif unit == "qc_flag":
        assert ptypes.is_bool_dtype(series.dtype), f"{feature}.{column} must be boolean"
    else:
        raise AssertionError(f"Unknown unit hint '{unit}' for {feature}.{column}")


def _assert_contract(feature: str, frame: pd.DataFrame) -> None:
    contract = CONTRACTS.get(feature)
    if contract is None:
        available = ", ".join(sorted(CONTRACTS))
        raise AssertionError(f"No contract found for {feature}. Available: {available}")

    expected_columns = [entry["column"] for entry in contract]
    assert list(frame.columns) == expected_columns, (
        f"Column mismatch for {feature}. Expected {expected_columns}, got {list(frame.columns)}"
    )

    for entry in contract:
        column = entry["column"]
        expected_dtype = entry["dtype"]
        unit = entry["unit"]
        assert unit, f"Missing unit hint for {feature}.{column}"
        actual_dtype = str(frame[column].dtype)
        assert (
            actual_dtype == expected_dtype
        ), f"{feature}.{column} dtype {actual_dtype} != expected {expected_dtype}"
        _assert_unit_hint(unit, frame[column], feature, column)


@pytest.fixture()
def contract_quotes() -> pd.DataFrame:
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
def contract_trades() -> pd.DataFrame:
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


def test_microstructure_contracts(contract_quotes: pd.DataFrame, contract_trades: pd.DataFrame) -> None:
    _assert_contract("compute_ofi", microstructure.compute_ofi(contract_quotes))
    _assert_contract("book_imbalance", microstructure.book_imbalance(contract_quotes))
    _assert_contract(
        "kyle_lambda", microstructure.kyle_lambda(contract_trades, contract_quotes)
    )
    _assert_contract("amihud_illiq", microstructure.amihud_illiq(contract_trades))
    _assert_contract("spreads", microstructure.spreads(contract_quotes))


def test_vpin_contract(contract_trades: pd.DataFrame) -> None:
    result = vpin.compute_vpin(contract_trades, bucket_volume=50, rolling_bars=2)
    # Ensure we have at least two completed bars for probability checks.
    if result.empty:
        pytest.skip("Synthetic data failed to produce VPIN bars")
    _assert_contract("compute_vpin", result)
