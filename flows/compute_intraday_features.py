"""Prefect flow to compute (placeholder) intraday microstructure features."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from prefect import flow, get_run_logger

from .compute_offexchange_features import compute_offexchange_features


@flow(name="compute-intraday-features")
def compute_intraday_features(
    trade_date: date,
    symbols: Sequence[str] | None = None,
    persist: bool = False,
) -> list[dict[str, object]]:
    """Reuse the off-exchange FINRA computation as a stand-in for intraday features."""

    logger = get_run_logger()
    logger.info(
        "compute_intraday_features placeholder delegating to compute_offexchange_features",
    )
    return compute_offexchange_features(trade_date=trade_date, symbols=symbols, persist=persist)


__all__ = ["compute_intraday_features"]
