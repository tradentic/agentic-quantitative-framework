from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from framework.alerts import Alert, dispatch_alert
from framework.sec_client import ParsedForm4, fetch_edgar_url, parse_form4_xml
from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client
from features.insider_helpers import is_ceo, is_recent_filing
from features.price_trend import PriceTrend, evaluate_price_trend
from utils.symbols import coerce_symbol_case

LOGGER = logging.getLogger(__name__)


def _fetch_recent_filings(symbol: str, since: date) -> list[dict[str, Any]]:
    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        return []
    response = (
        client.table("edgar_filings")
        .select("accession_number, filing_date, xml_url, reporter, symbol")
        .eq("symbol", symbol)
        .gte("filing_date", since.isoformat())
        .order("filing_date", desc=True)
        .execute()
    )
    data = getattr(response, "data", None)
    if data is None:
        data = response.get("data") if isinstance(response, dict) else None
    return list(data or [])


def _load_parsed_form4(filing: dict[str, Any]) -> ParsedForm4 | None:
    if "parsed" in filing and isinstance(filing["parsed"], ParsedForm4):
        return filing["parsed"]
    xml_bytes = filing.get("xml_bytes")
    xml_url = filing.get("xml_url")
    if xml_bytes is None:
        if not xml_url:
            return None
        try:
            xml_bytes = fetch_edgar_url(xml_url)
        except FileNotFoundError:
            LOGGER.warning("XML not found for accession %s", filing.get("accession_number"))
            return None
    try:
        parsed = parse_form4_xml(xml_bytes)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Failed to parse Form 4 XML for %s: %s", filing.get("accession_number"), exc)
        return None
    filing["parsed"] = parsed
    return parsed


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _summarize_filing(parsed: ParsedForm4) -> dict[str, Any]:
    filing_date = parsed.filing_date
    owner_name = parsed.reporting_owners[0].name if parsed.reporting_owners else parsed.reporter
    txn_code = parsed.transactions[0].code if parsed.transactions else None
    return {
        "date": (filing_date or date.today()).isoformat(),
        "owner": owner_name,
        "code": txn_code,
    }


def evaluate_nvda_insider_alert(
    symbol: str | None = None,
    *,
    lookback_days: int = 7,
    now: datetime | None = None,
    filings: Iterable[dict[str, Any]] | None = None,
    price_trend: PriceTrend | None = None,
    emit: bool = True,
) -> Alert | None:
    """Evaluate the NVDA insider alert rule and emit when conditions are met."""

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    symbol = coerce_symbol_case(symbol or "NVDA")
    start_date = now.date() - timedelta(days=max(lookback_days, 1))

    if filings is None:
        filings = _fetch_recent_filings(symbol, start_date)

    ceo_filings: list[dict[str, Any]] = []
    for filing in filings:
        parsed = _load_parsed_form4(filing)
        if parsed is None:
            continue
        if coerce_symbol_case(parsed.symbol) != symbol:
            continue
        filing_date = parsed.filing_date or _coerce_date(filing.get("filing_date"))
        if not is_recent_filing(filing_date, now, days=lookback_days):
            continue
        if not parsed.reporting_owners:
            continue
        if not any(is_ceo(owner) for owner in parsed.reporting_owners):
            continue
        ceo_filings.append(
            {
                "parsed": parsed,
                "summary": _summarize_filing(parsed),
                "filing_date": filing_date or now.date(),
            }
        )

    if not ceo_filings:
        return None

    price_trend = price_trend or evaluate_price_trend(symbol)
    if not price_trend.trend_up:
        return None

    latest = max(ceo_filings, key=lambda item: item["filing_date"])
    window = f"{start_date.isoformat()}..{now.date().isoformat()}"
    payload = {
        "symbol": symbol,
        "window": window,
        "ceo_filings": len(ceo_filings),
        "latest_filing": latest["summary"],
        "trend_up": price_trend.trend_up,
        "ret_5d": price_trend.ret_5d,
        "high_20d": price_trend.high_20d,
        "severity": "HIGH",
    }
    alert = Alert(symbol=symbol, severity="HIGH", payload=payload)
    if emit:
        dispatch_alert(alert)
    return alert


__all__ = ["evaluate_nvda_insider_alert"]
