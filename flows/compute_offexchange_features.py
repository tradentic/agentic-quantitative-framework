"""Prefect flow to compute FINRA off-exchange market structure features."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Sequence

from prefect import flow, get_run_logger, task

from framework.finra_client import FINRA_SHORT_VOLUME_MARKET, get_ats_week, get_short_volume
from framework.provenance import OFFEX_FEATURE_VERSION, hash_bytes, record_provenance
from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client


FINRA_BASE_URL = os.getenv("FINRA_BASE_URL", "https://cdn.finra.org/equity")


def _week_ending(trade_date: date) -> date:
    """Return the FINRA week-ending (Friday) date for a trading session."""

    weekday = trade_date.weekday()  # Monday=0
    offset = (4 - weekday) % 7
    return trade_date + timedelta(days=offset)


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    unique = {symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()}
    return sorted(unique)


@task
def load_candidate_symbols(trade_date: date, symbols: Sequence[str] | None = None) -> list[str]:
    logger = get_run_logger()
    if symbols:
        normalized = _normalize_symbols(symbols)
        logger.info("Using %d provided symbols for %s", len(normalized), trade_date)
        return normalized
    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        logger.warning("Supabase credentials missing; no symbols discovered for %s", trade_date)
        return []
    response = client.table("daily_features").select("symbol").eq("trade_date", trade_date.isoformat()).execute()
    data = getattr(response, "data", None) or []
    normalized = _normalize_symbols(row.get("symbol", "") for row in data)
    logger.info("Fetched %d symbols from daily_features for %s", len(normalized), trade_date)
    return normalized


def _compute_features(symbol: str, trade_date: date, week_ending: date) -> dict[str, object]:
    record = {
        "symbol": symbol,
        "trade_date": trade_date.isoformat(),
        "short_vol_share": None,
        "short_exempt_share": None,
        "ats_share_of_total": None,
    }
    short_volume = get_short_volume(symbol, trade_date)
    if short_volume:
        record["short_vol_share"] = short_volume.short_share
        record["short_exempt_share"] = short_volume.short_exempt_share
    ats_week = get_ats_week(symbol, week_ending)
    if ats_week:
        record["ats_share_of_total"] = ats_week.ats_share_of_total
    return record


def _build_short_volume_sources(trade_date: date) -> list[str]:
    stamp = trade_date.strftime("%Y%m%d")
    market = FINRA_SHORT_VOLUME_MARKET
    return [
        f"{FINRA_BASE_URL}/regsho/daily/{market}shvol{stamp}.txt",
        f"{FINRA_BASE_URL}/regsho/daily/{market}shvol{stamp}.txt.gz",
    ]


def _build_ats_sources(week_ending: date) -> list[str]:
    stamp = week_ending.strftime("%Y%m%d")
    return [
        f"{FINRA_BASE_URL}/ATS/ATS_W_Summary_{stamp}.zip",
        f"{FINRA_BASE_URL}/ATS/ATS_W_Summary_{stamp}.txt",
    ]


@task
def persist_features(trade_date: date, week_ending: date, rows: Sequence[dict[str, object]]) -> int:
    logger = get_run_logger()
    if not rows:
        logger.info("No off-exchange features to persist")
        return 0
    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        logger.warning("Supabase credentials missing; skipping persistence for %d rows", len(rows))
        return 0
    client.table("daily_features").upsert(list(rows), on_conflict="symbol,trade_date").execute()
    logger.info("Persisted %d off-exchange feature rows", len(rows))
    provenance_meta = {
        "feature_version": OFFEX_FEATURE_VERSION,
        "source_url": _build_short_volume_sources(trade_date) + _build_ats_sources(week_ending),
    }
    for row in rows:
        row_hash = hash_bytes(json.dumps(row, sort_keys=True, default=str).encode("utf-8"))
        metadata = provenance_meta | {
            "hash_sha256": row_hash,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        pk = {"symbol": row["symbol"], "trade_date": row["trade_date"]}
        record_provenance("daily_features", pk, metadata)
    return len(rows)


@flow(name="compute-offexchange-features")
def compute_offexchange_features(
    trade_date: date,
    symbols: Sequence[str] | None = None,
    persist: bool = True,
) -> list[dict[str, object]]:
    """Compute short volume and ATS share features for the requested trade date."""

    logger = get_run_logger()
    symbol_future = load_candidate_symbols.submit(trade_date, symbols)
    candidate_symbols = symbol_future.result()
    if not candidate_symbols:
        logger.info("No candidate symbols for %s", trade_date)
        return []
    week_end = _week_ending(trade_date)
    logger.info(
        "Computing off-exchange features for %d symbols on %s (week ending %s)",
        len(candidate_symbols),
        trade_date,
        week_end,
    )
    rows = [_compute_features(symbol, trade_date, week_end) for symbol in candidate_symbols]
    if persist:
        persist_features.submit(trade_date, week_end, rows).result()
    return rows


__all__ = ["compute_offexchange_features"]
