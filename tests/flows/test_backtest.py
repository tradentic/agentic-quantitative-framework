from __future__ import annotations

from pathlib import Path

import json

import numpy as np
import pandas as pd
import pytest

from flows.backtest import (
    InsiderBacktestConfig,
    build_labels,
    insider_prefiling_backtest,
    time_based_split,
)


def test_build_labels_assigns_positive_within_horizon() -> None:
    windows = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "window_end": [
                "2024-01-01",
                "2024-01-05",
                "2024-01-10",
            ],
            "feature": [1.0, 2.0, 3.0],
        }
    )
    filings = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "filing_date": ["2024-01-06", "2024-02-01"],
        }
    )

    labeled = build_labels(
        windows,
        filings,
        symbol_column="symbol",
        window_end_column="window_end",
        filing_symbol_column="symbol",
        filing_date_column="filing_date",
        horizon_days=7,
    )

    assert labeled["label"].tolist() == [1, 1, 0]
    assert pytest.approx(labeled.loc[0, "days_until_filing"], rel=1e-6) == 5.0


def test_time_based_split_is_chronological() -> None:
    frame = pd.DataFrame(
        {
            "window_end": pd.date_range("2024-01-01", periods=10, freq="D"),
            "value": np.arange(10),
        }
    )
    train_idx, val_idx = time_based_split(frame, time_column="window_end", validation_fraction=0.3)

    assert len(train_idx) + len(val_idx) == len(frame)
    assert max(frame.loc[train_idx, "window_end"]) < min(frame.loc[val_idx, "window_end"])


@pytest.mark.parametrize("file_format", ["csv", "parquet"])
def test_backtest_flow_creates_artifacts(tmp_path: Path, file_format: str) -> None:
    window_dates = pd.date_range("2024-01-01", periods=24, freq="D")
    windows = pd.DataFrame(
        {
            "symbol": ["AAA"] * 12 + ["BBB"] * 12,
            "window_end": window_dates,
            "feature_one": np.linspace(0, 1, len(window_dates)),
            "feature_two": np.linspace(1, 2, len(window_dates)),
        }
    )
    filings = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "filing_date": ["2024-01-10", "2024-01-20"],
        }
    )

    windows_path = tmp_path / f"windows.{file_format}"
    filings_path = tmp_path / f"filings.{file_format}"

    if file_format == "csv":
        windows.to_csv(windows_path, index=False)
        filings.to_csv(filings_path, index=False)
    else:
        pytest.importorskip("pyarrow")
        windows.to_parquet(windows_path, index=False)
        filings.to_parquet(filings_path, index=False)

    config = InsiderBacktestConfig(
        windows_path=windows_path,
        filings_path=filings_path,
        label_horizon_days=7,
        validation_fraction=0.25,
        report_dir=tmp_path,
        random_state=0,
        calibration_bins=3,
    )

    artifacts = insider_prefiling_backtest(config)

    assert artifacts.metrics_path.exists()
    assert artifacts.roc_curve_path.exists()
    assert artifacts.pr_curve_path.exists()
    assert artifacts.calibration_path.exists()

    payload = json.loads(artifacts.metrics_path.read_text())
    assert "models" in payload
    assert payload["models"], "Expected at least one model entry"
    assert payload["config"]["label_horizon_days"] == 7
    assert payload["config"]["model"] == "lightgbm"
    assert payload["config"]["mode"] == "train"
