from __future__ import annotations

from datetime import date
import logging
from datetime import date
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flows import ingest_sec_form4
from framework.sec_client import Form4IndexRow, Form4Transaction, ParsedForm4


class _DummyTable:
    def __init__(self, name: str, calls: dict[str, list[tuple[list[dict[str, object]], str | None]]]):
        self._name = name
        self._calls = calls

    def upsert(self, rows: list[dict[str, object]], on_conflict: str | None = None):
        self._calls.setdefault(self._name, []).append((rows, on_conflict))
        self._last_rows = rows
        return self

    def execute(self):
        return type("Response", (), {"data": self._last_rows})()


class _DummySupabase:
    def __init__(self):
        self.calls: dict[str, list[tuple[list[dict[str, object]], str | None]]] = {}

    def table(self, name: str) -> _DummyTable:
        return _DummyTable(name, self.calls)


@pytest.fixture(autouse=True)
def _patch_provenance(monkeypatch: pytest.MonkeyPatch):
    records: list[tuple[str, object, dict[str, object]] | tuple[str, object, None]] = []

    def _record(table: str, pk: object, meta: dict[str, object] | None = None) -> None:
        records.append((table, pk, meta or {}))

    monkeypatch.setattr(ingest_sec_form4, "record_provenance", _record)
    yield records


def test_ingest_form4_persists_schema(monkeypatch: pytest.MonkeyPatch, _patch_provenance):
    row = Form4IndexRow(
        form_type="4",
        company_name="Acme Inc",
        cik="0000123456",
        date_filed=date(2024, 12, 31),
        accession_number="0000123456-24-000001",
        accession_path="edgar/data/0000123456/0000123456-24-000001.txt",
    )
    parsed = ParsedForm4(
        symbol="acme",
        transactions=[
            Form4Transaction(date=date(2024, 12, 30), code="P", shares=100.0, price=10.5),
        ],
        reporter="John Doe",
        issuer_cik="0000123456",
        reporter_cik="0000554321",
        accession="0000123456-24-000001",
    )
    dummy = _DummySupabase()

    monkeypatch.setattr(ingest_sec_form4, "iter_form4_index", lambda _: [row])
    monkeypatch.setattr(ingest_sec_form4, "accession_to_primary_xml_url", lambda path: f"https://{path}")
    monkeypatch.setattr(ingest_sec_form4, "fetch_edgar_url", lambda url: b"<doc />")
    monkeypatch.setattr(ingest_sec_form4, "parse_form4_xml", lambda _: parsed)
    monkeypatch.setattr(ingest_sec_form4, "get_supabase_client", lambda: dummy)
    monkeypatch.setattr(ingest_sec_form4, "get_run_logger", lambda: logging.getLogger("test"))

    result = ingest_sec_form4.ingest_form4.fn(date_from=date(2024, 12, 31))

    assert result == {"filings": 1, "transactions": 1}
    filings_calls = dummy.calls["edgar_filings"]
    assert filings_calls[0][1] == "accession_number"
    filing_row = filings_calls[0][0][0]
    assert filing_row["accession_number"] == "0000123456-24-000001"
    assert filing_row["filing_date"] == "2024-12-31"
    assert filing_row["symbol"] == "ACME"
    assert filing_row["reporter"] == "John Doe"
    assert filing_row["reporter_cik"] == "0000554321"
    assert filing_row["xml_url"].startswith("https://")
    assert "payload_sha256" in filing_row and len(filing_row["payload_sha256"]) == 64

    transactions_calls = dummy.calls["insider_transactions"]
    assert transactions_calls[0][1] == "accession_number,transaction_date,transaction_code,symbol"
    transaction_row = transactions_calls[0][0][0]
    assert transaction_row["insider_name"] == "John Doe"
    assert transaction_row["reporter_cik"] == "0000554321"
    assert transaction_row["transaction_code"] == "P"
    assert transaction_row["transaction_date"] == "2024-12-30"


