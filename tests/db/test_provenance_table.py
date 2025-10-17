"""Integration-style tests for the provenance_events table contract."""

from __future__ import annotations

import copy
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # pragma: no branch - deterministic in tests
    sys.path.insert(0, str(ROOT))

from framework import provenance
from framework.provenance import record_provenance


class _InMemorySupabaseClient:
    """Very small in-memory stand-in for the Supabase Python client."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, object]]] = {}

    def table(self, name: str) -> "_TableAdapter":
        self._tables.setdefault(name, [])
        return _TableAdapter(self, name)

    def transaction(self) -> "_Transaction":
        return _Transaction(self)


class _Transaction:
    def __init__(self, client: _InMemorySupabaseClient) -> None:
        self._client = client
        self._snapshot: dict[str, list[dict[str, object]]] = copy.deepcopy(client._tables)

    def __enter__(self) -> _InMemorySupabaseClient:
        return self._client

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        if exc_type is not None:
            self._client._tables = self._snapshot
        return False


class _TableAdapter:
    def __init__(self, client: _InMemorySupabaseClient, name: str) -> None:
        self._client = client
        self._name = name
        self._result: list[dict[str, object]] = []

    def insert(self, rows):  # type: ignore[no-untyped-def]
        records = rows if isinstance(rows, list) else [rows]
        table = self._client._tables[self._name]
        for row in records:
            table.append(dict(row))
        self._result = list(table)
        return self

    def select(self, _columns="*"):
        table = self._client._tables[self._name]
        self._result = list(table)
        return self

    def execute(self):  # type: ignore[no-untyped-def]
        return types.SimpleNamespace(data=self._result)


@pytest.fixture
def transactional_supabase_client() -> _InMemorySupabaseClient:
    client = _InMemorySupabaseClient()
    with client.transaction() as txn:
        yield txn


def test_provenance_round_trip(transactional_supabase_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provenance, "get_supabase_client", lambda: transactional_supabase_client)

    observed_at = datetime(2024, 12, 31, 1, 5, tzinfo=timezone.utc).isoformat()
    record_provenance(
        "edgar_filings",
        "0000123456-24-000001",
        {
            "source_url": "https://www.sec.gov/Archives/edgar/data/0000123456/0000123456-24-000001/primary_doc.xml",
            "parser_version": provenance.FORM4_PARSER_VERSION,
            "payload_sha256": "d5a1f28b39b0eae8e6a4df7fcb5a0aa32a4ed3d8f4e5c1d5a1475413b90fd0a8",
            "observed_at": observed_at,
        },
    )

    response = (
        transactional_supabase_client
        .table(provenance.PROVENANCE_TABLE)
        .select("*")
        .execute()
    )
    rows = response.data
    assert len(rows) == 1
    record = rows[0]
    assert record["source"] == "edgar_filings"
    assert record["source_url"].endswith("primary_doc.xml")
    assert record["parser_version"] == provenance.FORM4_PARSER_VERSION
    assert record["artifact_sha256"] == "d5a1f28b39b0eae8e6a4df7fcb5a0aa32a4ed3d8f4e5c1d5a1475413b90fd0a8"
    body = record["payload"]
    assert body["record_id"] == "0000123456-24-000001"
    meta = body["meta"]
    assert isinstance(meta, dict)
    assert meta["observed_at"] == observed_at
    assert meta["parser_version"] == provenance.FORM4_PARSER_VERSION
    assert "fetched_at" in meta
