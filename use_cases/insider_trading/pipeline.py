"""Pipeline orchestration for the insider trading use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from use_cases.base import StrategyUseCase, UseCaseRequest


@dataclass
class InsiderTradingUseCase(StrategyUseCase):
    """Agent wiring for insider trading anomaly detection."""

    name: str = "insider_trading"
    description: str = "Detect anomalous trades around insider filings using Supabase-backed agents."

    def build_request(
        self,
        *,
        symbol: str,
        hypothesis: str,
        feature_candidates: List[Dict[str, Any]],
        backtest_window: Dict[str, Any],
    ) -> UseCaseRequest:
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
