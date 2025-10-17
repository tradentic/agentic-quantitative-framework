from __future__ import annotations

from datetime import date
from datetime import date
from pathlib import Path
import sys
import logging
import types

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flows.compute_offexchange_features import compute_offexchange_features, persist_features


class _DummyTable:
    def __init__(self, name: str, log: list[tuple[str, list[dict[str, object]], str | None]]):
        self._name = name
        self._log = log

    def upsert(self, rows: list[dict[str, object]], on_conflict: str | None = None):
        self._log.append((self._name, rows, on_conflict))
        self._last = rows
        return self

    def execute(self):
        return type("Response", (), {"data": self._last})()


class _DummySupabase:
    def __init__(self):
        self.log: list[tuple[str, list[dict[str, object]], str | None]] = []

    def table(self, name: str) -> _DummyTable:
        return _DummyTable(name, self.log)


@pytest.fixture(autouse=True)
def _no_supabase(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "flows.compute_offexchange_features.get_supabase_client",
        lambda: _DummySupabase(),
    )


def test_persist_features_adds_provenance(monkeypatch: pytest.MonkeyPatch):
    dummy = _DummySupabase()
    monkeypatch.setattr(
        "flows.compute_offexchange_features.get_supabase_client",
        lambda: dummy,
    )
    monkeypatch.setattr(
        "flows.compute_offexchange_features.get_run_logger",
        lambda: logging.getLogger("test"),
    )
    rows = [
        {
            "symbol": "ACME",
            "trade_date": "2024-12-30",
            "short_vol_share": 0.12,
            "short_exempt_share": 0.01,
            "ats_share_of_total": 0.25,
        }
    ]
    persisted = persist_features.fn(date(2024, 12, 30), date(2024, 12, 31), rows)
    assert persisted == 1
    name, payload, conflict = dummy.log[0]
    assert name == "daily_features"
    assert conflict == "symbol,trade_date,feature_version"
    assert payload[0]["feature_version"] == "offexchange-features-v1"
    assert payload[0]["provenance"]["feature_version"].startswith("offexchange")
    assert payload[0]["provenance"]["source_url"]


def test_flow_returns_rows_without_persist(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "flows.compute_offexchange_features.get_run_logger",
        lambda: logging.getLogger("test"),
    )
    class _Future:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    monkeypatch.setattr(
        "flows.compute_offexchange_features.load_candidate_symbols.submit",
        lambda trade_date, symbols: _Future(symbols or []),
    )
    monkeypatch.setattr(
        "flows.compute_offexchange_features.get_short_volume",
        lambda symbol, trade_date: types.SimpleNamespace(short_share=0.12, short_exempt_share=0.01),
    )
    monkeypatch.setattr(
        "flows.compute_offexchange_features.get_ats_week",
        lambda symbol, week_ending: types.SimpleNamespace(ats_share_of_total=0.25),
    )
    rows = compute_offexchange_features.fn(
        trade_date=date(2024, 12, 30), symbols=["ACME"], persist=False
    )
    assert isinstance(rows, list)
