"""Tests for Supabase client utilities."""

from __future__ import annotations

import types
from datetime import datetime, timedelta, timezone

import pytest

from framework.supabase_client import insert_embeddings


@pytest.mark.parametrize("window_minutes", [1])
def test_insert_embeddings_uses_conflict_key(monkeypatch: pytest.MonkeyPatch, window_minutes: int) -> None:
    captured: dict[str, object] = {}

    class _DummyTable:
        def upsert(self, rows, on_conflict=None):  # type: ignore[no-untyped-def]
            captured["rows"] = rows
            captured["on_conflict"] = on_conflict
            return self

        def execute(self):  # type: ignore[no-untyped-def]
            return types.SimpleNamespace(data=[{"id": "existing"}])

    class _DummyClient:
        def table(self, name: str) -> _DummyTable:
            captured["table"] = name
            return _DummyTable()

    monkeypatch.setattr(
        "framework.supabase_client.get_supabase_client", lambda: _DummyClient()
    )

    start = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    end = start + timedelta(minutes=window_minutes)
    payload = [
        {
            "asset_symbol": "ACME",
            "time_range": (start.isoformat(), end.isoformat()),
            "embedding": [0.0] * 128,
            "regime_tag": "demo",
            "label": {},
            "meta": {},
        }
    ]

    result = insert_embeddings(payload)

    assert result == [{"id": "existing"}]
    assert captured["table"] == "signal_embeddings"
    assert captured["on_conflict"] == "asset_symbol,time_range,emb_type,emb_version"
    rows = captured["rows"]
    assert isinstance(rows, list)
    assert rows[0]["asset_symbol"] == "ACME"
    assert rows[0]["time_range"].startswith("[")
    assert len(rows[0]["embedding"]) == 128
    assert rows[0]["emb_type"] == "ts2vec"
    assert rows[0]["emb_version"] == "v1"
    assert "updated_at" in rows[0]

