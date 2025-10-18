from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from framework.vendor_markets import create_market_data_client


@dataclass(frozen=True)
class PriceTrend:
    ret_5d: float
    high_20d: bool
    trend_up: bool

    def as_dict(self) -> dict[str, Any]:
        return {"ret_5d": self.ret_5d, "high_20d": self.high_20d, "trend_up": self.trend_up}


def get_price_series(symbol: str, start: datetime, end: datetime, interval: str = "1d") -> pd.Series:
    """Return a daily close price series for the provided window."""

    if interval != "1d":  # pragma: no cover - only daily supported
        raise ValueError("Only daily interval is supported")
    if start.tzinfo is None:
        raise ValueError("Start datetime must be timezone-aware")
    if end.tzinfo is None:
        raise ValueError("End datetime must be timezone-aware")
    client = create_market_data_client()
    trades = client.get_trades(symbol, start, end)
    if trades.empty:
        return pd.Series(dtype=float)
    trades = trades.copy()
    trades.sort_values("timestamp", inplace=True)
    trades.set_index("timestamp", inplace=True)
    closes = trades["price"].resample("1D").last().dropna()
    closes.index = closes.index.normalize()
    closes.name = "close"
    return closes


def calculate_price_trend(closes: pd.Series) -> PriceTrend:
    if closes.empty or len(closes) < 6:
        return PriceTrend(ret_5d=0.0, high_20d=False, trend_up=False)
    closes = closes.sort_index()
    latest = closes.iloc[-1]
    baseline = closes.iloc[-6]
    ret_5d = 0.0 if baseline == 0 else float(latest / baseline - 1)
    window = closes.iloc[-20:] if len(closes) >= 20 else closes
    high_20d = bool(latest >= window.max())
    trend_up = bool((ret_5d > 0) or high_20d)
    return PriceTrend(ret_5d=ret_5d, high_20d=high_20d, trend_up=trend_up)


def evaluate_price_trend(symbol: str, *, end: datetime | None = None) -> PriceTrend:
    end = end or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(days=40)
    closes = get_price_series(symbol, start, end)
    return calculate_price_trend(closes)


__all__ = ["PriceTrend", "calculate_price_trend", "evaluate_price_trend", "get_price_series"]
