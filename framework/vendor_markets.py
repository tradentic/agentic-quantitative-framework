"""Vendor market data abstractions for trades and NBBO quotes."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator, Protocol, Sequence

import pandas as pd
import requests

DEFAULT_VENDOR_ENV_VAR = "MARKET_VENDOR_SOURCE"
_POLYGON_DEFAULT_BASE_URL = os.getenv("POLYGON_REST_BASE_URL", "https://api.polygon.io")
_POLYGON_TIMEOUT = float(os.getenv("POLYGON_HTTP_TIMEOUT", "10"))
_POLYGON_PAGE_LIMIT = int(os.getenv("POLYGON_PAGE_LIMIT", "50000"))


class MarketDataClient(Protocol):
    """Protocol describing vendor market data capabilities."""

    def get_trades(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Return a tidy DataFrame of trade prints for the provided window."""

    def get_nbbo(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Return a tidy DataFrame of NBBO quotes for the provided window."""


@dataclass(slots=True)
class PolygonMarketDataClient:
    """Market data adapter for Polygon.io's v3 trades and quotes APIs."""

    api_key: str
    session: requests.Session | None = None
    base_url: str = _POLYGON_DEFAULT_BASE_URL

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("PolygonMarketDataClient requires a non-empty API key")
        if self.session is None:
            self.session = requests.Session()

    def get_trades(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch and normalize trades for the symbol between start and end."""

        start_utc, end_utc = _validate_window(start, end)
        params = {
            "timestamp.gte": _datetime_to_iso8601(start_utc),
            "timestamp.lt": _datetime_to_iso8601(end_utc),
            "limit": _POLYGON_PAGE_LIMIT,
            "sort": "timestamp",
            "order": "asc",
        }
        raw_records = list(
            self._paginate(f"/v3/trades/{symbol.upper()}", params=params)
        )
        return _normalize_trades(raw_records)

    def get_nbbo(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch and normalize NBBO quotes for the symbol between start and end."""

        start_utc, end_utc = _validate_window(start, end)
        params = {
            "timestamp.gte": _datetime_to_iso8601(start_utc),
            "timestamp.lt": _datetime_to_iso8601(end_utc),
            "limit": _POLYGON_PAGE_LIMIT,
            "sort": "timestamp",
            "order": "asc",
        }
        raw_records = list(
            self._paginate(f"/v3/quotes/{symbol.upper()}", params=params)
        )
        return _normalize_quotes(raw_records)

    def _paginate(self, path: str, params: dict[str, object]) -> Iterator[dict[str, object]]:
        url = f"{self.base_url}{path}"
        query_params = dict(params)
        query_params["apiKey"] = self.api_key
        while url:
            response = self.session.get(url, params=query_params, timeout=_POLYGON_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            for record in payload.get("results", []) or []:
                yield record
            next_url = payload.get("next_url")
            if next_url:
                url = next_url
                query_params = {"apiKey": self.api_key}
            else:
                url = ""


def create_market_data_client(default: str | None = None) -> MarketDataClient:
    """Instantiate a market data client using environment configuration."""

    vendor_name = (os.getenv(DEFAULT_VENDOR_ENV_VAR) or default or "").strip().lower()
    if vendor_name == "polygon":
        api_key = os.getenv("POLYGON_API_KEY")
        if not api_key:
            raise RuntimeError("POLYGON_API_KEY environment variable is required for Polygon client")
        return PolygonMarketDataClient(api_key=api_key)
    raise RuntimeError(
        f"Unsupported market data vendor '{vendor_name}'. Set {DEFAULT_VENDOR_ENV_VAR} to a supported value."
    )


def _validate_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start_utc = _ensure_utc(start)
    end_utc = _ensure_utc(end)
    if start_utc >= end_utc:
        raise ValueError("Start datetime must be before end datetime")
    return start_utc, end_utc


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Datetime arguments must be timezone-aware")
    return value.astimezone(timezone.utc)


def _datetime_to_iso8601(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_timestamp_ns(value: int | None) -> pd.Timestamp:
    if value is None:
        return pd.NaT
    return pd.to_datetime(value, unit="ns", utc=True)


def _normalize_conditions(raw: Iterable[int | str] | None) -> tuple[str, ...]:
    if raw is None:
        return tuple()
    return tuple(str(item) for item in raw)


def _normalize_trades(records: Iterable[dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in records:
        conditions = _normalize_conditions(record.get("conditions"))
        trf_timestamp = _to_timestamp_ns(record.get("trf_timestamp"))
        rows.append(
            {
                "timestamp": _to_timestamp_ns(record.get("sip_timestamp")),
                "price": record.get("price"),
                "size": record.get("size"),
                "exchange": record.get("exchange"),
                "conditions": conditions,
                "sequence_number": record.get("sequence_number"),
                "participant_timestamp": _to_timestamp_ns(record.get("participant_timestamp")),
                "trf_timestamp": trf_timestamp,
                "tape": record.get("tape"),
                "trade_id": record.get("id"),
                "trf_id": record.get("trf_id"),
                "is_off_exchange": pd.notna(trf_timestamp),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _normalize_quotes(records: Iterable[dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in records:
        trf_timestamp = _to_timestamp_ns(record.get("trf_timestamp"))
        rows.append(
            {
                "timestamp": _to_timestamp_ns(record.get("sip_timestamp")),
                "bid_price": record.get("bid_price"),
                "bid_size": record.get("bid_size"),
                "ask_price": record.get("ask_price"),
                "ask_size": record.get("ask_size"),
                "bid_exchange": record.get("bid_exchange"),
                "ask_exchange": record.get("ask_exchange"),
                "conditions": _normalize_conditions(record.get("conditions")),
                "sequence_number": record.get("sequence_number"),
                "participant_timestamp": _to_timestamp_ns(record.get("participant_timestamp")),
                "trf_timestamp": trf_timestamp,
                "tape": record.get("tape"),
                "is_off_exchange": pd.notna(trf_timestamp),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _parse_datetime(value: str) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.to_pydatetime()


def _run_cli(args: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch trades and NBBO quotes from configured vendor")
    parser.add_argument("symbol", help="Ticker symbol to query")
    parser.add_argument("start", help="ISO8601 start timestamp (inclusive)")
    parser.add_argument("end", help="ISO8601 end timestamp (exclusive)")
    parser.add_argument(
        "--vendor",
        default=None,
        help=f"Override vendor selection (defaults to ${DEFAULT_VENDOR_ENV_VAR})",
    )
    parsed = parser.parse_args(args)

    start = _parse_datetime(parsed.start)
    end = _parse_datetime(parsed.end)
    client = create_market_data_client(default=parsed.vendor)
    trades = client.get_trades(parsed.symbol, start, end)
    quotes = client.get_nbbo(parsed.symbol, start, end)

    print("Trades head:\n", trades.head())
    print("Quotes head:\n", quotes.head())
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI utility
    raise SystemExit(_run_cli())
