"""Microstructure feature engineering utilities."""

from __future__ import annotations

from typing import Iterable, Mapping

import numpy as np
import pandas as pd

_GROUP_COLS: tuple[str, str, str] = ("symbol", "date", "window")


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _empty_metric_result(metric: str, extras: Mapping[str, str] | None = None) -> pd.DataFrame:
    columns: dict[str, pd.Series] = {
        "symbol": pd.Series(dtype="object"),
        "date": pd.Series(dtype="object"),
        "window": pd.Series(dtype="object"),
        metric: pd.Series(dtype="float64"),
    }
    if extras:
        for name, dtype in extras.items():
            columns[name] = pd.Series(dtype=dtype)
    return pd.DataFrame(columns)


def compute_ofi(quotes: pd.DataFrame) -> pd.DataFrame:
    """Compute order flow imbalance (OFI) per (symbol, date, window)."""

    required_cols = [
        *_GROUP_COLS,
        "timestamp",
        "bid_price",
        "bid_size",
        "ask_price",
        "ask_size",
    ]
    _require_columns(quotes, required_cols)

    if quotes.empty:
        return _empty_metric_result("ofi", {"ofi_obs": "int64", "ofi_qc_pass": "boolean"})

    quotes_sorted = quotes.sort_values(list(_GROUP_COLS) + ["timestamp"])
    rows: list[dict[str, object]] = []

    for key, group in quotes_sorted.groupby(list(_GROUP_COLS), sort=False):
        group_sorted = group.sort_values("timestamp").reset_index(drop=True)
        prev_bid_price = group_sorted["bid_price"].shift(1)
        prev_bid_size = group_sorted["bid_size"].shift(1)
        prev_ask_price = group_sorted["ask_price"].shift(1)
        prev_ask_size = group_sorted["ask_size"].shift(1)

        bid_contrib = np.where(
            group_sorted["bid_price"] > prev_bid_price,
            group_sorted["bid_size"],
            np.where(
                group_sorted["bid_price"] < prev_bid_price,
                -prev_bid_size,
                group_sorted["bid_size"] - prev_bid_size,
            ),
        )

        ask_contrib = np.where(
            group_sorted["ask_price"] < prev_ask_price,
            group_sorted["ask_size"],
            np.where(
                group_sorted["ask_price"] > prev_ask_price,
                -prev_ask_size,
                group_sorted["ask_size"] - prev_ask_size,
            ),
        )

        first_obs = prev_bid_price.isna()
        bid_contrib[first_obs] = 0.0
        ask_contrib[first_obs] = 0.0

        ofi_series = bid_contrib - ask_contrib
        ofi_value = float(np.nansum(ofi_series))
        obs_count = int(len(group_sorted))
        qc_pass = bool(obs_count >= 2 and np.isfinite(ofi_value))

        rows.append(
            {
                "symbol": key[0],
                "date": key[1],
                "window": key[2],
                "ofi": ofi_value,
                "ofi_obs": obs_count,
                "ofi_qc_pass": qc_pass,
            }
        )

    return pd.DataFrame(rows)


def book_imbalance(quotes: pd.DataFrame) -> pd.DataFrame:
    """Compute end-of-window book imbalance."""

    required_cols = [
        *_GROUP_COLS,
        "timestamp",
        "bid_size",
        "ask_size",
    ]
    _require_columns(quotes, required_cols)

    if quotes.empty:
        return _empty_metric_result(
            "book_imbalance",
            {"book_imbalance_obs": "int64", "book_imbalance_qc_pass": "boolean"},
        )

    quotes_sorted = quotes.sort_values(list(_GROUP_COLS) + ["timestamp"])
    rows: list[dict[str, object]] = []

    for key, group in quotes_sorted.groupby(list(_GROUP_COLS), sort=False):
        group_sorted = group.sort_values("timestamp")
        last_row = group_sorted.iloc[-1]
        bid_size = float(last_row["bid_size"])
        ask_size = float(last_row["ask_size"])
        denom = bid_size + ask_size
        imbalance = np.nan if denom == 0 else (bid_size - ask_size) / denom
        qc_pass = bool(denom > 0 and np.isfinite(imbalance))

        rows.append(
            {
                "symbol": key[0],
                "date": key[1],
                "window": key[2],
                "book_imbalance": imbalance,
                "book_imbalance_obs": int(len(group_sorted)),
                "book_imbalance_qc_pass": qc_pass,
            }
        )

    return pd.DataFrame(rows)


def kyle_lambda(trades: pd.DataFrame, nbbo: pd.DataFrame) -> pd.DataFrame:
    """Estimate Kyle's lambda per window using trade-to-NBBO alignment."""

    trade_required = [*_GROUP_COLS, "timestamp", "price", "size"]
    nbbo_required = [*_GROUP_COLS, "timestamp", "bid_price", "ask_price"]
    _require_columns(trades, trade_required)
    _require_columns(nbbo, nbbo_required)

    if trades.empty:
        return _empty_metric_result(
            "kyle_lambda", {"kyle_lambda_obs": "int64", "kyle_lambda_qc_pass": "boolean"}
        )

    trades_sorted = trades.sort_values(list(_GROUP_COLS) + ["timestamp"]).copy()
    nbbo_sorted = nbbo.sort_values(list(_GROUP_COLS) + ["timestamp"]).copy()
    nbbo_sorted["mid_price"] = (nbbo_sorted["bid_price"] + nbbo_sorted["ask_price"]) / 2

    nbbo_groups = {
        key: group[["timestamp", "mid_price"]].sort_values("timestamp")
        for key, group in nbbo_sorted.groupby(list(_GROUP_COLS), sort=False)
    }

    rows: list[dict[str, object]] = []

    for key, trade_group in trades_sorted.groupby(list(_GROUP_COLS), sort=False):
        trade_sorted = trade_group.sort_values("timestamp").reset_index(drop=True)
        nbbo_group = nbbo_groups.get(key)

        if nbbo_group is None or nbbo_group.empty:
            rows.append(
                {
                    "symbol": key[0],
                    "date": key[1],
                    "window": key[2],
                    "kyle_lambda": np.nan,
                    "kyle_lambda_obs": 0,
                    "kyle_lambda_qc_pass": False,
                }
            )
            continue

        merged = pd.merge_asof(
            trade_sorted,
            nbbo_group,
            on="timestamp",
            direction="backward",
        )

        merged["mid_price"] = merged["mid_price"].astype(float)
        signed_volume = merged["size"] * np.sign(merged["price"] - merged["mid_price"])
        price_change = merged["price"].diff()

        mask = price_change.notna() & (signed_volume != 0) & (merged["size"] > 0)
        valid_ratios = (price_change.abs() / signed_volume.abs()).where(mask).dropna()

        obs_count = int(len(valid_ratios))
        lambda_value = float(valid_ratios.median()) if obs_count > 0 else np.nan
        qc_pass = bool(obs_count >= 1 and np.isfinite(lambda_value))

        rows.append(
            {
                "symbol": key[0],
                "date": key[1],
                "window": key[2],
                "kyle_lambda": lambda_value,
                "kyle_lambda_obs": obs_count,
                "kyle_lambda_qc_pass": qc_pass,
            }
        )

    return pd.DataFrame(rows)


def amihud_illiq(trades: pd.DataFrame) -> pd.DataFrame:
    """Compute the Amihud (2002) illiquidity ratio per window."""

    trade_required = [*_GROUP_COLS, "timestamp", "price", "size"]
    _require_columns(trades, trade_required)

    if trades.empty:
        return _empty_metric_result(
            "amihud_illiq", {"amihud_obs": "int64", "amihud_qc_pass": "boolean"}
        )

    trades_sorted = trades.sort_values(list(_GROUP_COLS) + ["timestamp"])
    rows: list[dict[str, object]] = []

    for key, group in trades_sorted.groupby(list(_GROUP_COLS), sort=False):
        group_sorted = group.sort_values("timestamp").reset_index(drop=True)
        returns = group_sorted["price"].pct_change().abs()
        dollar_volume = group_sorted["price"] * group_sorted["size"]
        mask = returns.notna() & (dollar_volume > 0)

        ratios = (returns / dollar_volume).where(mask).dropna()
        obs_count = int(len(ratios))
        illiq_value = float(ratios.mean()) if obs_count > 0 else np.nan
        qc_pass = bool(obs_count >= 1 and np.isfinite(illiq_value))

        rows.append(
            {
                "symbol": key[0],
                "date": key[1],
                "window": key[2],
                "amihud_illiq": illiq_value,
                "amihud_obs": obs_count,
                "amihud_qc_pass": qc_pass,
            }
        )

    return pd.DataFrame(rows)


def spreads(nbbo: pd.DataFrame) -> pd.DataFrame:
    """Compute average absolute and relative spreads per window."""

    nbbo_required = [*_GROUP_COLS, "timestamp", "bid_price", "ask_price"]
    _require_columns(nbbo, nbbo_required)

    if nbbo.empty:
        return _empty_metric_result(
            "avg_spread",
            {"avg_rel_spread": "float64", "spreads_obs": "int64", "spreads_qc_pass": "boolean"},
        )

    nbbo_sorted = nbbo.sort_values(list(_GROUP_COLS) + ["timestamp"])
    rows: list[dict[str, object]] = []

    for key, group in nbbo_sorted.groupby(list(_GROUP_COLS), sort=False):
        group_sorted = group.sort_values("timestamp").reset_index(drop=True)
        spread = group_sorted["ask_price"] - group_sorted["bid_price"]
        mid = (group_sorted["ask_price"] + group_sorted["bid_price"]) / 2
        mask = (spread >= 0) & (mid > 0)

        valid_spread = spread[mask]
        valid_rel_spread = (spread / mid)[mask]
        obs_count = int(len(valid_spread))

        avg_spread = float(valid_spread.mean()) if obs_count > 0 else np.nan
        avg_rel_spread = float(valid_rel_spread.mean()) if obs_count > 0 else np.nan
        qc_pass = bool(obs_count >= 1 and np.isfinite(avg_spread) and np.isfinite(avg_rel_spread))

        rows.append(
            {
                "symbol": key[0],
                "date": key[1],
                "window": key[2],
                "avg_spread": avg_spread,
                "avg_rel_spread": avg_rel_spread,
                "spreads_obs": obs_count,
                "spreads_qc_pass": qc_pass,
            }
        )

    return pd.DataFrame(rows)
