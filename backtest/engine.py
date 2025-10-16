"""Lightweight backtest engine used by autonomous agents and Prefect flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class BacktestRun:
    """In-memory container for backtest results."""

    strategy_id: str
    equity_curve: list[float]
    summary: dict[str, float]


def _max_drawdown(equity: np.ndarray) -> float:
    peaks = np.maximum.accumulate(equity)
    drawdowns = (equity - peaks) / peaks
    return float(drawdowns.min())


def _run_price_simulation(config: dict[str, Any]) -> np.ndarray:
    horizon = int(config.get("horizon", 60))
    mu = float(config.get("expected_return", 0.001))
    sigma = float(config.get("volatility", 0.02))
    seed = int(config.get("seed", 42))
    rng = np.random.default_rng(seed)
    returns = rng.normal(mu, sigma, size=horizon)
    equity = np.cumprod(1 + returns)
    return equity


def _summarize_equity(equity: np.ndarray) -> dict[str, float]:
    pct_returns = np.diff(equity) / equity[:-1]
    if pct_returns.size == 0:
        pct_returns = np.array([0.0])
    mean_return = float(np.mean(pct_returns))
    volatility = float(np.std(pct_returns) + 1e-8)
    sharpe = mean_return / volatility * np.sqrt(252)
    max_dd = _max_drawdown(equity)
    annualized_periods = max(len(equity), 1)
    annual_return = float((equity[-1] / equity[0]) ** (252 / annualized_periods) - 1)
    return {
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "annual_return": annual_return,
        "final_equity": float(equity[-1]),
    }


def run_backtest(config: dict[str, Any]) -> dict[str, Any]:
    """Execute a simulation and return both metrics and equity curve."""

    if "strategy_id" not in config:
        raise ValueError("Backtest config must include a `strategy_id`.")

    equity = _run_price_simulation(config)
    summary = _summarize_equity(equity)

    run = BacktestRun(
        strategy_id=config["strategy_id"],
        equity_curve=equity.tolist(),
        summary=summary,
    )
    return {
        "summary": run.summary,
        "equity_curve": run.equity_curve,
    }


__all__ = ["run_backtest"]
