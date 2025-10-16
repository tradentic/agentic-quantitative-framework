"""Use case registry for the Agentic Quantitative Framework."""

from use_cases.base import StrategyUseCase, UseCaseRequest
from use_cases.insider_trading.pipeline import InsiderTradingUseCase

__all__ = [
    "StrategyUseCase",
    "UseCaseRequest",
    "InsiderTradingUseCase",
]
