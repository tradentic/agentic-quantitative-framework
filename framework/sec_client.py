"""Deterministic SEC Form 4 client utilities for EDGAR ingestion."""

from __future__ import annotations

import gzip
import io
import os
import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Iterable, Iterator

import requests

from framework.sec_parse import (
    ReportingOwner,
    find_text,
    parse_filing_date,
    parse_issuer_name,
    parse_reporting_owners,
)

EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/"
DAILY_INDEX_BASE = f"{EDGAR_ARCHIVES_BASE}edgar/daily-index"
DEFAULT_USER_AGENT = os.getenv("SEC_HTTP_USER_AGENT") or os.getenv("SEC_USER_AGENT") or (
    "agentic-quantitative-framework/0.1 (+https://github.com/agentic-quantitative-framework)"
)
DEFAULT_TIMEOUT = float(os.getenv("SEC_HTTP_TIMEOUT", "10"))
DEFAULT_RETRIES = int(os.getenv("SEC_HTTP_RETRIES", "3"))
DEFAULT_RETRY_BACKOFF = float(os.getenv("SEC_HTTP_BACKOFF", "0.5"))


class EdgarHTTPError(RuntimeError):
    """Raised when the EDGAR API returns a non-retryable error."""


@dataclass(frozen=True)
class Form4IndexRow:
    """Structured representation of a Form 4 entry from the daily index."""

    form_type: str
    company_name: str
    cik: str
    date_filed: date
    accession_number: str
    accession_path: str


@dataclass(frozen=True)
class Form4Transaction:
    """Normalized Form 4 transaction record extracted from XML."""

    date: date
    code: str
    shares: float | None
    price: float | None


@dataclass(frozen=True)
class ParsedForm4:
    """Parsed representation of the Form 4 XML document."""

    symbol: str
    transactions: list[Form4Transaction]
    reporter: str
    issuer_cik: str
    reporter_cik: str
    accession: str
    issuer_name: str | None = None
    filing_date: date | None = None
    reporting_owners: tuple[ReportingOwner, ...] = tuple()


_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": DEFAULT_USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    return _session


def fetch_edgar_url(url: str) -> bytes:
    """Fetch raw bytes from EDGAR with retry and deterministic headers."""

    session = _get_session()
    last_error: Exception | None = None
    delay = DEFAULT_RETRY_BACKOFF
    for attempt in range(1, max(DEFAULT_RETRIES, 1) + 1):
        try:
            response = session.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 404:
                raise FileNotFoundError(url)
            if response.status_code >= 400:
                raise EdgarHTTPError(f"EDGAR request failed with status {response.status_code} for {url}")
            return response.content
        except (requests.RequestException, EdgarHTTPError, FileNotFoundError) as exc:
            last_error = exc
            if isinstance(exc, (EdgarHTTPError, FileNotFoundError)) or attempt >= max(DEFAULT_RETRIES, 1):
                raise
            time.sleep(delay)
            delay *= 2
    if last_error is not None:
        raise last_error
    raise EdgarHTTPError(f"Unknown error fetching {url}")


def _decode_index_bytes(content: bytes, url: str) -> str:
    if url.endswith(".gz") or content.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
            return stream.read().decode("latin-1")
    return content.decode("latin-1")


def daily_index_urls(target_date: date) -> list[str]:
    """Return deterministic EDGAR daily index URLs for a given calendar date."""

    quarter = (target_date.month - 1) // 3 + 1
    day_stamp = target_date.strftime("%Y%m%d")
    base = f"{DAILY_INDEX_BASE}/{target_date.year}/QTR{quarter}/form.{day_stamp}"
    return [f"{base}.idx", f"{base}.idx.gz"]


def _split_index_line(line: str) -> tuple[str, str, str, str, str] | None:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 5:
        return None
    return parts[0], parts[1], parts[2], parts[3], parts[4]


def iter_form4_index(target_date: date) -> Iterator[Form4IndexRow]:
    """Yield Form 4 rows for the provided filing date using the EDGAR daily index."""

    yielded = False
    for url in daily_index_urls(target_date):
        try:
            raw = fetch_edgar_url(url)
        except FileNotFoundError:
            continue
        text = _decode_index_bytes(raw, url)
        start_idx = None
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if line.lower().startswith("form type|"):
                start_idx = idx + 1
                break
        if start_idx is None:
            continue
        for line in lines[start_idx:]:
            if not line.strip():
                continue
            split = _split_index_line(line)
            if not split:
                continue
            form_type, company, cik, filed, filename = split
            if form_type.upper() not in {"4", "4/A"}:
                continue
            try:
                filed_date = datetime.strptime(filed, "%Y-%m-%d").date()
            except ValueError:
                continue
            accession_path = filename.lstrip("/")
            accession_number = accession_path.split("/")[-1]
            if accession_number.endswith(".txt"):
                accession_number = accession_number[:-4]
            yield Form4IndexRow(
                form_type=form_type,
                company_name=company,
                cik=cik,
                date_filed=filed_date,
                accession_number=accession_number,
                accession_path=accession_path,
            )
            yielded = True
        if yielded:
            break


def accession_to_primary_xml_url(acc_path: str) -> str:
    """Map an accession path from the index into the canonical primary XML URL."""

    normalized = acc_path.lstrip("/")
    if normalized.endswith(".xml"):
        return f"{EDGAR_ARCHIVES_BASE}{normalized}"
    if normalized.endswith(".txt"):
        normalized = normalized[:-4]
    if normalized.endswith("-index"):
        normalized = normalized[: -len("-index")]
    if "." in normalized.split("/")[-1]:
        # The path still points to a file (likely the submission text). Use its parent directory.
        parent = "/".join(normalized.split("/")[:-1])
    else:
        parent = normalized
    if not parent:
        raise ValueError(f"Could not derive primary XML path from accession {acc_path!r}")
    candidate = f"{parent}/primary_doc.xml"
    return f"{EDGAR_ARCHIVES_BASE}{candidate}"


def _iter_transactions(root: Iterable) -> Iterator[Form4Transaction]:
    for table_name in ("nonDerivativeTransaction", "derivativeTransaction"):
        for node in root.iter():
            if isinstance(getattr(node, "tag", None), str) and node.tag.split("}")[-1] == table_name:
                date_text = find_text(node, "transactionDate")
                code = find_text(node, "transactionCode")
                shares = _coerce_float(find_text(node, "transactionShares"))
                price = _coerce_float(find_text(node, "transactionPricePerShare"))
                if not date_text or not code:
                    continue
                try:
                    txn_date = datetime.strptime(date_text.strip(), "%Y-%m-%d").date()
                except ValueError:
                    continue
                yield Form4Transaction(date=txn_date, code=code.strip(), shares=shares, price=price)


def _coerce_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def parse_form4_xml(xml_bytes: bytes) -> ParsedForm4:
    """Parse a Form 4 XML document into the normalized payload used by the framework."""

    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    symbol = find_text(root, "issuerTradingSymbol") or ""
    reporter = find_text(root, "rptOwnerName") or ""
    issuer_cik = find_text(root, "issuerCik") or ""
    reporter_cik = find_text(root, "rptOwnerCik") or ""
    accession = find_text(root, "accessionNumber") or ""
    issuer_name = parse_issuer_name(root)
    filing_date = parse_filing_date(root)
    reporting_owners = parse_reporting_owners(root)
    transactions = list(_iter_transactions(root))
    return ParsedForm4(
        symbol=symbol,
        transactions=transactions,
        reporter=reporter,
        issuer_cik=issuer_cik,
        reporter_cik=reporter_cik,
        accession=accession,
        issuer_name=issuer_name,
        filing_date=filing_date,
        reporting_owners=reporting_owners,
    )


__all__ = [
    "Form4IndexRow",
    "Form4Transaction",
    "ParsedForm4",
    "daily_index_urls",
    "iter_form4_index",
    "accession_to_primary_xml_url",
    "parse_form4_xml",
    "fetch_edgar_url",
]
