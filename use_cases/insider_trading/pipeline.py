"""Pipeline orchestration for the insider trading use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from use_cases.base import StrategyUseCase, UseCaseRequest


@dataclass
class InsiderTradingUseCase(StrategyUseCase):
    """Agent wiring for insider trading anomaly detection."""

    name: str = "insider_trading"
    description: str = (
        "Detect anomalous trades around insider filings using Supabase-backed agents."
    )

    def build_request(self, **kwargs: Any) -> UseCaseRequest:
        symbol = str(kwargs.get("symbol", "")).strip()
        hypothesis = str(kwargs.get("hypothesis", "")).strip()
        feature_candidates = kwargs.get("feature_candidates") or []
        backtest_window = kwargs.get("backtest_window") or {}

        if not symbol:
            raise ValueError("`symbol` is required for the insider trading use case.")
        if not hypothesis:
            raise ValueError("`hypothesis` is required to describe the feature context.")

        payload = {
            "name": f"{symbol}-insider-anomaly",
            "description": hypothesis,
            "metadata": {
                "symbol": symbol,
                "feature_candidates": feature_candidates,
                "backtest_window": backtest_window,
            },
        }
        return UseCaseRequest(intent="propose_new_feature", payload=payload)
