"""Prefect flow to ingest SEC Form 4 filings into Supabase."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
import xml.etree.ElementTree as ET

from prefect import flow, get_run_logger

from observability.otel import init_tracing

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
def ingest_form4(date_from: date, date_to: date | None = None) -> dict[str, int]:
    """Ingest Form 4 filings between two dates (inclusive)."""

    logger = get_run_logger()
    if date_to is None:
        date_to = date_from
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")

    logger.info("Starting Form 4 ingest from %s to %s", date_from, date_to)
    total_filings = 0
    total_transactions = 0
    persistence_available = True
    try:
        get_supabase_client()
    except MissingSupabaseConfiguration:
        logger.warning("Supabase credentials not configured; running in dry-run mode")
        persistence_available = False

    flow_attributes = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
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
                                parsed = ParsedForm4(
                                    symbol=parsed.symbol,
                                    transactions=parsed.transactions,
                                    reporter=parsed.reporter,
                                    issuer_cik=parsed.issuer_cik or row.cik,
                                    reporter_cik=parsed.reporter_cik,
                                    accession=row.accession_number,
                                )
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
                date_span.set_attribute("total_filings", total_filings)
                date_span.set_attribute("total_transactions", total_transactions)
            logger.info(
                "%s -> %d filings persisted, %d transactions",
                target_date,
                total_filings,
                total_transactions,
            )
    return {"filings": total_filings, "transactions": total_transactions}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest SEC Form 4 filings into Supabase")
    parser.add_argument("--date", type=str, help="Single date (YYYY-MM-DD) to ingest")
    parser.add_argument("--date-from", type=str, help="Start date inclusive (YYYY-MM-DD)")
    parser.add_argument("--date-to", type=str, help="End date inclusive (YYYY-MM-DD)")
    return parser.parse_args()


def _coerce_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


if __name__ == "__main__":
    args = _parse_args()
    if args.date:
        start = end = _coerce_date(args.date)
    else:
        start = _coerce_date(args.date_from)
        end = _coerce_date(args.date_to) if args.date_to else start
    if start is None:
        raise SystemExit("--date or --date-from is required")
    if end is None:
        end = start
    result = ingest_form4(date_from=start, date_to=end)
    print(result)
