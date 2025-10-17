"""Unit tests for the provenance helpers."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # pragma: no branch - executed deterministically in tests
    sys.path.insert(0, str(ROOT))

from framework import provenance
from framework.provenance import hash_bytes, record_provenance
from framework.supabase_client import MissingSupabaseConfiguration


def test_hash_bytes_matches_stdlib() -> None:
    payload = b"agentic-framework"
    assert hash_bytes(payload) == hashlib.sha256(payload).hexdigest()


def test_hash_bytes_rejects_non_bytes() -> None:
    with pytest.raises(TypeError):
        hash_bytes("not-bytes")  # type: ignore[arg-type]


def test_record_provenance_handles_missing_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    def raiser() -> None:
        raise MissingSupabaseConfiguration("missing credentials")

    monkeypatch.setattr(provenance, "get_supabase_client", raiser)
    record_provenance("example", "pk", {"source_url": "http://example.com"})


def test_record_provenance_inserts_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyQuery:
        def insert(self, payload):  # type: ignore[no-untyped-def]
            captured["payload"] = payload
            return self

        def execute(self):  # type: ignore[no-untyped-def]
            return type("Response", (), {"data": [{"ok": True}]})()

    class DummyClient:
        def table(self, name):  # type: ignore[no-untyped-def]
            captured["table"] = name
            return DummyQuery()

    monkeypatch.setattr(provenance, "get_supabase_client", lambda: DummyClient())
    now = datetime.now(timezone.utc)
    meta = {"source_url": "http://example.com", "observed_at": now, "parser_version": "v1"}
    record_provenance("edgar_filings", {"id": 1}, meta)

    payload = captured["payload"]
    assert captured["table"] == provenance.PROVENANCE_TABLE
    assert payload["source"] == "edgar_filings"
    assert payload["source_url"] == "http://example.com"
    assert payload["parser_version"] == "v1"
    body = payload["payload"]
    assert body["record_id"] == '{"id": 1}'
    assert body["meta"]["source_url"] == "http://example.com"
    assert "fetched_at" in body["meta"]
    assert body["meta"]["observed_at"].endswith("+00:00")
