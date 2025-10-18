"""Prefect flow to ingest SEC Form 4 filings into Supabase."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from prefect import flow, get_run_logger

from observability.otel import init_tracing

from framework.config import DEFAULT_ISSUER_CIK, DEFAULT_SYMBOL
from framework.provenance import FORM4_PARSER_VERSION, hash_bytes, record_provenance
from framework.sec_client import (
    Form4IndexRow,
    ParsedForm4,
    accession_to_primary_xml_url,
    fetch_edgar_url,
    iter_form4_index,
    parse_form4_xml,
)
from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client
from utils.symbols import coerce_symbol_case

tracer = init_tracing("flow-ingest-sec-form4")

BATCH_SIZE = max(int(os.getenv("SEC_FORM4_BATCH_SIZE", "50")), 1)


def _daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _build_filing_record(row: Form4IndexRow, parsed: ParsedForm4, xml_url: str) -> dict[str, object]:
    accession = parsed.accession or row.accession_number
    filing_date = row.date_filed
    filed_at = filing_date.isoformat()
    symbol = coerce_symbol_case(parsed.symbol)
    canonical = {
        "accession_number": accession,
        "cik": parsed.issuer_cik or row.cik,
        "form_type": row.form_type,
        "company_name": row.company_name,
        "filing_date": filing_date.isoformat(),
        "filed_at": filed_at,
        "symbol": symbol or None,
        "reporter": (parsed.reporter or "").strip() or None,
        "reporter_cik": (parsed.reporter_cik or "").strip() or None,
        "xml_url": xml_url,
    }
    payload_hash = hash_bytes(
        json.dumps({k: v for k, v in canonical.items() if k != "filed_at"}, sort_keys=True).encode("utf-8")
    )
    canonical["payload_sha256"] = payload_hash
    return canonical


def _build_transaction_records(parsed: ParsedForm4) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for txn in parsed.transactions:
        payload.append(
            {
                "accession_number": parsed.accession,
                "transaction_date": txn.date.isoformat(),
                "transaction_code": txn.code,
                "shares": txn.shares,
                "price": txn.price,
                "symbol": coerce_symbol_case(parsed.symbol) or None,
                "insider_name": parsed.reporter,
                "reporter_cik": parsed.reporter_cik or None,
            }
        )
    return payload


def _chunked(iterable: list[Form4IndexRow], size: int) -> Iterable[list[Form4IndexRow]]:
    for idx in range(0, len(iterable), size):
        yield iterable[idx : idx + size]


def _persist_records(table: str, records: list[dict[str, object]], *, conflict: str | None = None) -> int:
    if not records:
        return 0
    client = get_supabase_client()
    attributes = {"table": table, "rows": len(records)}
    if conflict:
        attributes["on_conflict"] = conflict
    with tracer.start_as_current_span("supabase.upsert", attributes=attributes):
        if conflict:
            client.table(table).upsert(records, on_conflict=conflict).execute()
        else:
            client.table(table).upsert(records).execute()
    return len(records)


@flow(name="ingest-sec-form4")
def ingest_form4(
    date_from: date,
    date_to: date | None = None,
    *,
    symbol_filter: str | None = None,
    persist: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    """Ingest Form 4 filings between two dates (inclusive)."""

    logger = get_run_logger()
    if date_to is None:
        date_to = date_from
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")

    symbol_filter = coerce_symbol_case(symbol_filter) if symbol_filter else None
    logger.info("Starting Form 4 ingest from %s to %s", date_from, date_to)
    total_filings = 0
    total_transactions = 0
    matched_filings = 0
    persistence_available = persist
    if persist:
        try:
            get_supabase_client()
        except MissingSupabaseConfiguration:
            logger.warning("Supabase credentials not configured; running in dry-run mode")
            persistence_available = False

    flow_attributes = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
    should_stop = False
    with tracer.start_as_current_span("flow.ingest_form4", attributes=flow_attributes):
        for target_date in _daterange(date_from, date_to):
            rows = list(iter_form4_index(target_date))
            logger.info("%s -> %d Form 4 candidates", target_date, len(rows))
            date_attributes = {
                "target_date": target_date.isoformat(),
                "candidate_count": len(rows),
            }
            with tracer.start_as_current_span(
                "ingest.process_date",
                attributes=date_attributes,
            ) as date_span:
                for batch in _chunked(rows, BATCH_SIZE):
                    filings_payload: list[dict[str, object]] = []
                    transactions_payload: list[dict[str, object]] = []
                    batch_provenance: list[tuple[str, dict[str, object] | str, dict[str, object]]] = []
                    batch_attributes = {"batch_size": len(batch)}
                    with tracer.start_as_current_span(
                        "ingest.process_batch", attributes=batch_attributes
                    ) as batch_span:
                        for row in batch:
                            xml_url = accession_to_primary_xml_url(row.accession_path)
                            try:
                                fetched_at = datetime.now(timezone.utc).isoformat()
                                xml_bytes = fetch_edgar_url(xml_url)
                            except FileNotFoundError:
                                logger.warning(
                                    "Missing primary XML for accession %s", row.accession_number
                                )
                                continue
                            try:
                                parsed = parse_form4_xml(xml_bytes)
                            except ET.ParseError as exc:
                                logger.warning(
                                    "Failed to parse Form 4 XML for accession %s: %s",
                                    row.accession_number,
                                    exc,
                                )
                                continue
                            if not parsed.accession:
                                parsed = replace(
                                    parsed,
                                    accession=row.accession_number,
                                    issuer_cik=parsed.issuer_cik or row.cik,
                                )
                            parsed_symbol = coerce_symbol_case(parsed.symbol)
                            if symbol_filter and parsed_symbol != symbol_filter:
                                continue
                            xml_hash = hash_bytes(xml_bytes)
                            filing_record = _build_filing_record(row, parsed, xml_url)
                            filing_record["xml_sha256"] = xml_hash
                            filing_record["provenance"] = {
                                "parser_version": FORM4_PARSER_VERSION,
                                "source_url": xml_url,
                                "fetched_at": fetched_at,
                            }
                            filings_payload.append(filing_record)
                            filing_meta = {
                                "source_url": xml_url,
                                "xml_sha256": xml_hash,
                                "parser_version": FORM4_PARSER_VERSION,
                                "fetched_at": fetched_at,
                                "payload_sha256": filing_record.get("payload_sha256"),
                            }
                            batch_provenance.append(
                                (
                                    "edgar_filings",
                                    {"accession_number": filing_record["accession_number"]},
                                    filing_meta,
                                )
                            )
                            for txn_record in _build_transaction_records(parsed):
                                transactions_payload.append(txn_record)
                                txn_key = {
                                    "accession_number": txn_record["accession_number"],
                                    "transaction_date": txn_record["transaction_date"],
                                    "transaction_code": txn_record["transaction_code"],
                                    "symbol": txn_record["symbol"],
                                }
                                batch_provenance.append(
                                    ("insider_transactions", txn_key, filing_meta)
                                )
                            matched_filings += 1
                            if limit and matched_filings >= limit:
                                should_stop = True
                                break
                        batch_filings = len(filings_payload)
                        batch_transactions = len(transactions_payload)
                        batch_span.set_attribute("filings", batch_filings)
                        batch_span.set_attribute("transactions", batch_transactions)
                        if persistence_available:
                            total_filings += _persist_records(
                                "edgar_filings", filings_payload, conflict="accession_number"
                            )
                            total_transactions += _persist_records(
                                "insider_transactions",
                                transactions_payload,
                                conflict="accession_number,transaction_date,transaction_code,symbol",
                            )
                            for table_name, pk, meta in batch_provenance:
                                record_provenance(table_name, pk, meta)
                        else:
                            total_filings += batch_filings
                            total_transactions += batch_transactions
                        if should_stop:
                            break
                date_span.set_attribute("total_filings", total_filings)
                date_span.set_attribute("total_transactions", total_transactions)
            logger.info(
                "%s -> %d filings persisted, %d transactions",
                target_date,
                total_filings,
                total_transactions,
            )
            if should_stop:
                break
    return {"filings": total_filings, "transactions": total_transactions}


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest SEC Form 4 filings into Supabase",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--date", type=str, help="Single date (YYYY-MM-DD) to ingest")
    parser.add_argument("--date-from", type=str, help="Start date inclusive (YYYY-MM-DD)")
    parser.add_argument("--date-to", type=str, help="End date inclusive (YYYY-MM-DD)")
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help="Target issuer symbol (default: %(default)s)",
    )
    parser.add_argument(
        "--xml-url",
        help="Process a single Form 4 by primary XML URL (overrides date range)",
    )
    parser.add_argument(
        "--accession",
        help=(
            "Accession number or archive path for a single Form 4. "
            "Falls back to DEFAULT_ISSUER_CIK when resolving."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum filings to ingest when using --date or date range",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Supabase persistence and only parse filings",
    )
    parser.add_argument(
        "--issuer-cik",
        default=DEFAULT_ISSUER_CIK,
        help="Override issuer CIK when resolving accessions",
    )
    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return _build_arg_parser().parse_args(argv)


def _coerce_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _derive_accession_number(parsed: ParsedForm4, xml_url: str) -> str:
    if parsed.accession:
        return parsed.accession
    path = urlparse(xml_url).path
    filename = path.split("/")[-1]
    stem = filename.split(".")[0] if filename else ""
    if stem.endswith("-index"):
        stem = stem[: -len("-index")]
    return stem or parsed.accession or ""


def _build_row_from_parsed(parsed: ParsedForm4, xml_url: str, issuer_cik: str | None) -> Form4IndexRow:
    accession_number = _derive_accession_number(parsed, xml_url)
    path = urlparse(xml_url).path.lstrip("/") or accession_number
    cik = parsed.issuer_cik or (issuer_cik or "")
    try:
        cik = str(int(cik)) if cik else cik
    except ValueError:
        cik = cik
    filing_date = parsed.filing_date or date.today()
    return Form4IndexRow(
        form_type="4",
        company_name=parsed.issuer_name or "",
        cik=cik or "",
        date_filed=filing_date,
        accession_number=accession_number or path.split("/")[-1],
        accession_path=path,
    )


def _ingest_single_xml(
    xml_url: str,
    *,
    symbol_filter: str | None,
    persist: bool,
    issuer_cik: str | None,
    xml_bytes: bytes | None = None,
) -> dict[str, int]:
    logger = get_run_logger()
    fetched_at = datetime.now(timezone.utc).isoformat()
    if xml_bytes is None:
        xml_bytes = fetch_edgar_url(xml_url)
    parsed = parse_form4_xml(xml_bytes)
    parsed_symbol = coerce_symbol_case(parsed.symbol)
    if symbol_filter and parsed_symbol != symbol_filter:
        logger.info("Skipping Form 4 for %s due to symbol filter %s", parsed_symbol, symbol_filter)
        return {"filings": 0, "transactions": 0}
    row = _build_row_from_parsed(parsed, xml_url, issuer_cik)
    parsed = replace(
        parsed,
        accession=row.accession_number,
        issuer_cik=parsed.issuer_cik or row.cik,
    )
    xml_hash = hash_bytes(xml_bytes)
    filing_record = _build_filing_record(row, parsed, xml_url)
    filing_record["xml_sha256"] = xml_hash
    filing_record["provenance"] = {
        "parser_version": FORM4_PARSER_VERSION,
        "source_url": xml_url,
        "fetched_at": fetched_at,
    }
    filings_payload = [filing_record]
    transactions_payload = _build_transaction_records(parsed)
    filing_meta = {
        "source_url": xml_url,
        "xml_sha256": xml_hash,
        "parser_version": FORM4_PARSER_VERSION,
        "fetched_at": fetched_at,
        "payload_sha256": filing_record.get("payload_sha256"),
    }
    persistence_available = persist
    if persist:
        try:
            get_supabase_client()
        except MissingSupabaseConfiguration:
            logger.warning("Supabase credentials not configured; running in dry-run mode")
            persistence_available = False
    if persistence_available:
        filings = _persist_records("edgar_filings", filings_payload, conflict="accession_number")
        transactions = _persist_records(
            "insider_transactions",
            transactions_payload,
            conflict="accession_number,transaction_date,transaction_code,symbol",
        )
        record_provenance("edgar_filings", {"accession_number": filing_record["accession_number"]}, filing_meta)
        for txn in transactions_payload:
            txn_key = {
                "accession_number": txn["accession_number"],
                "transaction_date": txn["transaction_date"],
                "transaction_code": txn["transaction_code"],
                "symbol": txn["symbol"],
            }
            record_provenance("insider_transactions", txn_key, filing_meta)
    else:
        filings = len(filings_payload)
        transactions = len(transactions_payload)
    return {"filings": filings, "transactions": transactions}


def _candidate_xml_urls(accession: str, issuer_cik: str | None) -> list[str]:
    normalized = accession.strip()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return [normalized]
    if normalized.lower().endswith(".xml") and not normalized.startswith("http"):
        return [f"https://www.sec.gov/Archives/{normalized.lstrip('/')}"]
    if normalized.lower().startswith("edgar/"):
        primary = accession_to_primary_xml_url(normalized)
        return [primary]
    if "/" in normalized and not normalized.lower().endswith(".xml"):
        primary = accession_to_primary_xml_url(normalized)
        return [primary]
    cleaned = normalized.split(".")[0]
    if cleaned.endswith("-index"):
        cleaned = cleaned[: -len("-index")]
    accession_nodash = cleaned.replace("-", "")
    bases: list[str] = []
    if issuer_cik:
        stripped_cik = issuer_cik.lstrip("0") or issuer_cik
        bases.append(f"https://www.sec.gov/Archives/edgar/data/{stripped_cik}/{accession_nodash}")
    bases.append(f"https://www.sec.gov/Archives/edgar/data/{accession_nodash}/{cleaned}")
    filenames = [
        "primary_doc.xml",
        "doc4.xml",
        "form4.xml",
        "xslForm4.xml",
        f"{cleaned}.xml",
    ]
    urls = []
    for base in bases:
        for filename in filenames:
            urls.append(f"{base.rstrip('/')}/{filename}")
    return urls


def _resolve_accession_to_xml(accession: str, issuer_cik: str | None) -> tuple[str, bytes]:
    for candidate in _candidate_xml_urls(accession, issuer_cik):
        try:
            xml_bytes = fetch_edgar_url(candidate)
            return candidate, xml_bytes
        except FileNotFoundError:
            continue
    raise FileNotFoundError(f"Unable to resolve accession {accession!r} to a Form 4 XML")


def main(argv: list[str] | None = None) -> dict[str, int] | None:
    args = _parse_args(argv)
    symbol_value = (args.symbol or "").strip()
    symbol_filter = coerce_symbol_case(symbol_value) if symbol_value else None
    issuer_cik = (args.issuer_cik or "").strip() or DEFAULT_ISSUER_CIK or None
    persist = not args.dry_run
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be a positive integer")

    if args.xml_url:
        return _ingest_single_xml(
            args.xml_url,
            symbol_filter=symbol_filter,
            persist=persist,
            issuer_cik=issuer_cik,
        )
    if args.accession:
        xml_url, xml_bytes = _resolve_accession_to_xml(args.accession, issuer_cik)
        return _ingest_single_xml(
            xml_url,
            symbol_filter=symbol_filter,
            persist=persist,
            issuer_cik=issuer_cik,
            xml_bytes=xml_bytes,
        )

    if args.date:
        start = end = _coerce_date(args.date)
    else:
        start = _coerce_date(args.date_from)
        end = _coerce_date(args.date_to) if args.date_to else start
    if start is None:
        raise SystemExit("--date or --date-from is required")
    if end is None:
        end = start
    return ingest_form4(
        date_from=start,
        date_to=end,
        symbol_filter=symbol_filter,
        persist=persist,
        limit=args.limit,
    )


if __name__ == "__main__":
    output = main()
    if output is not None:
        print(output)
