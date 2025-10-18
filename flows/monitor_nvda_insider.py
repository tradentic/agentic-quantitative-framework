from __future__ import annotations

from prefect import flow, get_run_logger

from alerts.insider_nvda import evaluate_nvda_insider_alert
from framework.config import DEFAULT_SYMBOL


@flow(name="monitor-nvda-insider")
def monitor_nvda_insider(symbol: str | None = None):
    """Prefect flow that evaluates the NVDA insider alert rule."""

    logger = get_run_logger()
    target_symbol = symbol or DEFAULT_SYMBOL
    alert = evaluate_nvda_insider_alert(symbol=target_symbol)
    if alert is None:
        logger.info("No insider alert generated for %s", target_symbol)
        return None
    payload = alert.to_dict()
    logger.info(
        "Emitted NVDA insider alert severity=%s filings=%s",
        alert.severity,
        alert.payload.get("ceo_filings"),
    )
    return payload


__all__ = ["monitor_nvda_insider"]
