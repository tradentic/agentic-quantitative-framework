"""VPIN (Volume-Synchronized Probability of Informed Trading) features."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

import numpy as np
import pandas as pd

_GROUP_COLS: tuple[str, str, str] = ("symbol", "date", "window")


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _empty_vpin_result() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": pd.Series(dtype="object"),
            "date": pd.Series(dtype="object"),
            "window": pd.Series(dtype="object"),
            "vpin": pd.Series(dtype="float64"),
            "vpin_change": pd.Series(dtype="float64"),
            "vpin_obs": pd.Series(dtype="int64"),
            "vpin_qc_pass": pd.Series(dtype="boolean"),
        }
    )


def _tick_rule_sign(prices: pd.Series) -> pd.Series:
    """Infer trade direction using the tick rule."""

    price_diff = prices.astype(float).diff()
    sign = pd.Series(np.sign(price_diff.to_numpy()), index=prices.index, dtype="float64")
    sign.replace(0.0, np.nan, inplace=True)
    sign = sign.ffill()

    if sign.empty:
        return sign

    if pd.isna(sign.iloc[0]):
        sign.iloc[0] = 1.0

    sign = sign.ffill()
    sign.fillna(1.0, inplace=True)
    return sign


@dataclass
class _VolumeBar:
    """Representation of a volume-synchronised bar."""

    end_time: pd.Timestamp
    buy_volume: float
    sell_volume: float
    total_volume: float


def _generate_volume_bars(group: pd.DataFrame, bucket_volume: float) -> Iterator[_VolumeBar]:
    if bucket_volume <= 0:
        raise ValueError("bucket_volume must be positive")

    group_sorted = group.sort_values("timestamp").reset_index(drop=True)
    signs = _tick_rule_sign(group_sorted["price"]).to_numpy()
    sizes = group_sorted["size"].astype(float).to_numpy()
    timestamps = pd.to_datetime(group_sorted["timestamp"]).to_numpy()

    current_volume = 0.0
    buy_volume = 0.0
    sell_volume = 0.0

    for sign, size, ts in zip(signs, sizes, timestamps):
        remaining = float(size)
        trade_sign = 1.0 if sign >= 0 else -1.0

        while remaining > 0:
            available = bucket_volume - current_volume
            take = remaining if remaining <= available else available

            if trade_sign > 0:
                buy_volume += take
            else:
                sell_volume += take

            current_volume += take
            remaining -= take

            if np.isclose(current_volume, bucket_volume) or current_volume > bucket_volume:
                yield _VolumeBar(
                    end_time=pd.Timestamp(ts),
                    buy_volume=buy_volume,
                    sell_volume=sell_volume,
                    total_volume=bucket_volume,
                )
                current_volume = 0.0
                buy_volume = 0.0
                sell_volume = 0.0

    # Drop incomplete bucket (if any) by design.


def compute_vpin(
    trades: pd.DataFrame,
    *,
    bucket_volume: float,
    rolling_bars: int,
) -> pd.DataFrame:
    """Compute VPIN and its change across (symbol, date, window) groups.

    Parameters
    ----------
    trades:
        Trade prints containing at least ``symbol``, ``date``, ``window``, ``timestamp``, ``price``,
        and ``size`` columns.
    bucket_volume:
        Target volume per bar used for synchronising trades.
    rolling_bars:
        Number of consecutive volume bars used to compute the VPIN rolling mean.

    Returns
    -------
    pandas.DataFrame
        Frame containing VPIN levels and changes for each (symbol, date, window).
    """

    required_cols = [*_GROUP_COLS, "timestamp", "price", "size"]
    _require_columns(trades, required_cols)

    if trades.empty:
        return _empty_vpin_result()

    if rolling_bars <= 0:
        raise ValueError("rolling_bars must be positive")

    trades_sorted = trades.sort_values(list(_GROUP_COLS) + ["timestamp"]).copy()

    rows: list[dict[str, object]] = []

    for key, group in trades_sorted.groupby(list(_GROUP_COLS), sort=False):
        bars = list(_generate_volume_bars(group, bucket_volume))
        obs_count = len(bars)

        if obs_count == 0:
            rows.append(
                {
                    "symbol": key[0],
                    "date": key[1],
                    "window": key[2],
                    "vpin": np.nan,
                    "vpin_change": np.nan,
                    "vpin_obs": 0,
                    "vpin_qc_pass": False,
                }
            )
            continue

        bar_frame = pd.DataFrame([bar.__dict__ for bar in bars])
        bar_frame["imbalance"] = (
            (bar_frame["buy_volume"] - bar_frame["sell_volume"]).abs() / bar_frame["total_volume"]
        )
        bar_frame["vpin"] = bar_frame["imbalance"].rolling(
            window=rolling_bars, min_periods=rolling_bars
        ).mean()
        bar_frame["vpin_change"] = bar_frame["vpin"].diff()

        valid_rows = bar_frame.dropna(subset=["vpin"])
        if valid_rows.empty:
            vpin_value = np.nan
            vpin_change_value = np.nan
            qc_pass = False
        else:
            last_row = valid_rows.iloc[-1]
            vpin_value = float(last_row["vpin"])
            vpin_change_value = (
                float(last_row["vpin_change"])
                if pd.notna(last_row["vpin_change"])
                else np.nan
            )
            qc_pass = bool(obs_count >= rolling_bars and np.isfinite(vpin_value))

        rows.append(
            {
                "symbol": key[0],
                "date": key[1],
                "window": key[2],
                "vpin": vpin_value,
                "vpin_change": vpin_change_value,
                "vpin_obs": obs_count,
                "vpin_qc_pass": qc_pass,
            }
        )

    return pd.DataFrame(rows)
