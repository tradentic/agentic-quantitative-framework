"""HTTP client helpers for FINRA short volume and ATS datasets."""

from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

import requests

FINRA_BASE_URL = os.getenv("FINRA_BASE_URL", "https://cdn.finra.org/equity")
FINRA_SHORT_VOLUME_MARKET = os.getenv("FINRA_SHORT_VOLUME_MARKET", "TOT").upper()
DEFAULT_TIMEOUT = float(os.getenv("FINRA_HTTP_TIMEOUT", "10"))
DEFAULT_RETRIES = int(os.getenv("FINRA_HTTP_RETRIES", "3"))
DEFAULT_BACKOFF = float(os.getenv("FINRA_HTTP_BACKOFF", "0.5"))
DEFAULT_USER_AGENT = os.getenv("FINRA_HTTP_USER_AGENT") or (
    "agentic-quantitative-framework/0.1 (+https://github.com/agentic-quantitative-framework)"
)

_FIELD_ALIASES = {
    "shortvolume": "short_volume",
    "shortexemptvolume": "short_exempt_volume",
    "totalvolume": "total_volume",
    "totalsharevolume": "total_volume",
    "totalweeklysharevolume": "total_weekly_share_volume",
    "totalweeklytradecount": "total_weekly_trade_count",
    "sharevolume": "shares",
    "weekending": "week",
}


class FinraHTTPError(RuntimeError):
    """Raised when FINRA responds with an unrecoverable HTTP status code."""


@dataclass(frozen=True)
class FinraShortVolume:
    """Normalized representation of a FINRA Reg SHO short volume record."""

    symbol: str
    trade_date: date
    short_volume: int
    short_exempt_volume: int
    total_volume: int

    @property
    def short_share(self) -> float | None:
        """Return the short volume as a fraction of reported total volume."""

        if self.total_volume <= 0:
            return None
        return self.short_volume / self.total_volume

    @property
    def short_exempt_share(self) -> float | None:
        """Return the short exempt volume as a fraction of reported total volume."""

        if self.total_volume <= 0:
            return None
        return self.short_exempt_volume / self.total_volume


@dataclass(frozen=True)
class FinraAtsWeek:
    """Aggregated weekly ATS share volume for a single symbol."""

    symbol: str
    week_ending: date
    ats_share_volume: int
    total_weekly_share_volume: int | None
    ats_trade_count: int
    total_weekly_trade_count: int | None

    @property
    def ats_share_of_total(self) -> float | None:
        """Return ATS market share as a ratio of reported total share volume."""

        if not self.total_weekly_share_volume or self.total_weekly_share_volume <= 0:
            return None
        return self.ats_share_volume / self.total_weekly_share_volume


_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        session = requests.Session()
        session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        })
        _session = session
    return _session


def _fetch_url(url: str) -> bytes:
    delay = DEFAULT_BACKOFF
    last_error: Exception | None = None
    for attempt in range(1, max(DEFAULT_RETRIES, 1) + 1):
        session = _get_session()
        try:
            response = session.get(url, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:  # pragma: no cover - network failure branch
            last_error = exc
            if attempt >= max(DEFAULT_RETRIES, 1):
                raise
            try:
                session.close()
            finally:  # pragma: no branch - ensure reset occurs
                _reset_session()
            _sleep(delay)
            delay *= 2
            continue
        if response.status_code == 404:
            raise FileNotFoundError(url)
        if response.status_code >= 400:
            raise FinraHTTPError(f"FINRA request failed with status {response.status_code}: {url}")
        return response.content
    if last_error:
        raise last_error
    raise FinraHTTPError(f"Unknown error fetching FINRA resource: {url}")


def _sleep(delay: float) -> None:
    """Indirection to allow monkeypatching during tests."""

    import time

    time.sleep(delay)


def _reset_session() -> None:
    global _session
    if _session is not None:
        try:
            _session.close()
        except Exception:  # pragma: no cover - defensive
            pass
    _session = None


def _try_urls(urls: list[str]) -> bytes:
    last_error: Exception | None = None
    for url in urls:
        try:
            return _fetch_url(url)
        except FileNotFoundError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise FinraHTTPError("No FINRA resource available for requested date")


def _normalize_key(key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower())
    collapsed = normalized.replace("_", "")
    if collapsed in _FIELD_ALIASES:
        return _FIELD_ALIASES[collapsed]
    if normalized in _FIELD_ALIASES:
        return _FIELD_ALIASES[normalized]
    return normalized


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    text = text.replace(",", "")
    if "." in text:
        return int(float(text))
    try:
        return int(text)
    except ValueError:
        return 0


def _decode_text(content: bytes, *, encoding: str = "utf-8") -> str:
    return content.decode(encoding, errors="ignore").lstrip("\ufeff")


def _read_zip(content: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        extracted: dict[str, str] = {}
        for name in archive.namelist():
            if not name.lower().endswith((".txt", ".csv")):
                continue
            extracted[name] = _decode_text(archive.read(name))
        if not extracted:
            raise ValueError("ZIP archive did not contain a text payload")
        return extracted


def _build_short_volume_urls(trade_date: date) -> list[str]:
    stamp = trade_date.strftime("%Y%m%d")
    market = FINRA_SHORT_VOLUME_MARKET
    return [
        f"{FINRA_BASE_URL}/regsho/daily/{market}shvol{stamp}.txt",
        f"{FINRA_BASE_URL}/regsho/daily/{market}shvol{stamp}.txt.gz",
    ]


def _parse_short_volume(content: str, trade_date: date) -> dict[str, FinraShortVolume]:
    reader = csv.DictReader(io.StringIO(content), delimiter="|")
    records: dict[str, FinraShortVolume] = {}
    for row in reader:
        normalized = {_normalize_key(key): value for key, value in row.items()}
        symbol = str(normalized.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        short_volume = _to_int(normalized.get("short_volume"))
        short_exempt_volume = _to_int(normalized.get("short_exempt_volume"))
        total_volume = _to_int(normalized.get("total_volume"))
        records[symbol] = FinraShortVolume(
            symbol=symbol,
            trade_date=trade_date,
            short_volume=short_volume,
            short_exempt_volume=short_exempt_volume,
            total_volume=total_volume,
        )
    return records


@lru_cache(maxsize=32)
def _short_volume_by_symbol(trade_date: date) -> dict[str, FinraShortVolume]:
    content = _try_urls(_build_short_volume_urls(trade_date))
    if content.startswith(b"PK\x03\x04"):
        files = _read_zip(content)
        # Use the first extracted text payload
        text = next(iter(files.values()))
    else:
        text = _decode_text(content)
    return _parse_short_volume(text, trade_date)


def get_short_volume(symbol: str, trade_date: date) -> FinraShortVolume | None:
    """Return the FINRA short volume record for a given symbol and date."""

    records = _short_volume_by_symbol(trade_date)
    return records.get(symbol.upper())


def _build_ats_urls(week_ending: date) -> list[str]:
    stamp = week_ending.strftime("%Y%m%d")
    return [
        f"{FINRA_BASE_URL}/ATS/ATS_W_Summary_{stamp}.zip",
        f"{FINRA_BASE_URL}/ATS/ATS_W_Summary_{stamp}.txt",
    ]


def _parse_ats_week(content: str, week_ending: date) -> dict[str, FinraAtsWeek]:
    reader = csv.DictReader(io.StringIO(content), delimiter="|")
    aggregates: dict[str, dict[str, Any]] = {}
    for row in reader:
        normalized = {_normalize_key(key): value for key, value in row.items()}
        symbol = str(normalized.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        share_volume = _to_int(
            normalized.get("shares")
            or normalized.get("share_volume")
            or normalized.get("weekly_share_volume")
            or normalized.get("total_weekly_share_volume_symbol")
        )
        trade_count = _to_int(
            normalized.get("trades")
            or normalized.get("trade_count")
            or normalized.get("weekly_trade_count")
        )
        total_share_volume = normalized.get("total_weekly_share_volume")
        total_trade_count = normalized.get("total_weekly_trade_count")
        aggregate = aggregates.setdefault(
            symbol,
            {
                "ats_share_volume": 0,
                "ats_trade_count": 0,
                "total_weekly_share_volume": None,
                "total_weekly_trade_count": None,
            },
        )
        aggregate["ats_share_volume"] += share_volume
        aggregate["ats_trade_count"] += trade_count
        if total_share_volume:
            volume_value = _to_int(total_share_volume)
            if volume_value:
                aggregate["total_weekly_share_volume"] = volume_value
        if total_trade_count:
            trade_value = _to_int(total_trade_count)
            if trade_value:
                aggregate["total_weekly_trade_count"] = trade_value
    results: dict[str, FinraAtsWeek] = {}
    for symbol, payload in aggregates.items():
        results[symbol] = FinraAtsWeek(
            symbol=symbol,
            week_ending=week_ending,
            ats_share_volume=payload["ats_share_volume"],
            total_weekly_share_volume=payload["total_weekly_share_volume"],
            ats_trade_count=payload["ats_trade_count"],
            total_weekly_trade_count=payload["total_weekly_trade_count"],
        )
    return results


@lru_cache(maxsize=32)
def _ats_week_by_symbol(week_ending: date) -> dict[str, FinraAtsWeek]:
    content = _try_urls(_build_ats_urls(week_ending))
    if content.startswith(b"PK\x03\x04"):
        files = _read_zip(content)
        text = next(iter(files.values()))
    else:
        text = _decode_text(content)
    return _parse_ats_week(text, week_ending)


def get_ats_week(symbol: str, week_ending: date) -> FinraAtsWeek | None:
    """Return the aggregated ATS week summary for a symbol."""

    records = _ats_week_by_symbol(week_ending)
    return records.get(symbol.upper())


__all__ = [
    "FinraHTTPError",
    "FinraShortVolume",
    "FinraAtsWeek",
    "get_short_volume",
    "get_ats_week",
]
