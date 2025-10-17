"""Tests verifying embedding upsert semantics across types."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from framework.supabase_client import insert_embeddings


@pytest.fixture
def fake_datetime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide deterministic timestamps for the insert_embeddings helper."""

    real_datetime = datetime

    class _FakeDatetime(datetime):
        queue = [
            real_datetime(2024, 1, 1, 0, 0, 0),
            real_datetime(2024, 1, 1, 0, 5, 0),
            real_datetime(2024, 1, 1, 0, 10, 0),
        ]

        @classmethod
        def utcnow(cls) -> datetime:
            if cls.queue:
                return cls.queue.pop(0)
            return real_datetime(2024, 1, 1, 0, 15, 0)

    monkeypatch.setattr("framework.supabase_client.datetime", _FakeDatetime)


def test_upsert_refreshes_rows_and_allows_multiple_types(
    fake_datetime: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated inserts update existing rows while new types coexist."""

    store: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    class _FakeTable:
        def upsert(  # type: ignore[no-untyped-def]
            self, rows, on_conflict=None
        ):
            assert on_conflict == "asset_symbol,time_range,emb_type,emb_version"
            for row in rows:
                key = (
                    row["asset_symbol"],
                    row["time_range"],
                    row["emb_type"],
                    row["emb_version"],
                )
                store[key] = dict(row)
            return self

        def execute(self):  # type: ignore[no-untyped-def]
            return SimpleNamespace(data=list(store.values()))

    class _FakeClient:
        def table(self, name: str) -> _FakeTable:
            assert name == "signal_embeddings"
            return _FakeTable()

    monkeypatch.setattr(
        "framework.supabase_client.get_supabase_client", lambda: _FakeClient()
    )

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(minutes=5)
    base_payload = {
        "asset_symbol": "ACME",
        "time_range": (start.isoformat(), end.isoformat()),
        "embedding": [0.0] * 128,
        "emb_type": "ts2vec",
        "emb_version": "v1",
    }

    insert_embeddings([base_payload])

    key_default = (
        "ACME",
        "[2024-01-01T00:00:00+00:00,2024-01-01T00:05:00+00:00)",
        "ts2vec",
        "v1",
    )
    assert key_default in store
    assert store[key_default]["updated_at"] == "2024-01-01T00:00:00+00:00"

    updated_payload = {
        **base_payload,
        "embedding": [1.0] + [0.0] * 127,
    }

    insert_embeddings([updated_payload])

    assert store[key_default]["embedding"][0] == 1.0
    assert store[key_default]["updated_at"] == "2024-01-01T00:05:00+00:00"

    alt_payload = {
        **base_payload,
        "emb_type": "deeplob",
        "emb_version": "research-v1",
        "embedding": [2.0] + [0.0] * 127,
    }

    insert_embeddings([alt_payload])

    alt_key = (
        "ACME",
        "[2024-01-01T00:00:00+00:00,2024-01-01T00:05:00+00:00)",
        "deeplob",
        "research-v1",
    )
    assert alt_key in store
    assert store[alt_key]["embedding"][0] == 2.0
    assert store[alt_key]["updated_at"] == "2024-01-01T00:10:00+00:00"
