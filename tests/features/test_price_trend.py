import pandas as pd

from features.price_trend import PriceTrend, calculate_price_trend


def test_calculate_price_trend_rising_series():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    prices = pd.Series(range(100, 130), index=dates, dtype=float)
    trend = calculate_price_trend(prices)
    assert isinstance(trend, PriceTrend)
    assert trend.trend_up is True
    assert trend.high_20d is True
    assert trend.ret_5d > 0


def test_calculate_price_trend_insufficient_data():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    prices = pd.Series([100.0, 101.0, 102.0], index=dates)
    trend = calculate_price_trend(prices)
    assert trend.trend_up is False
    assert trend.ret_5d == 0.0
