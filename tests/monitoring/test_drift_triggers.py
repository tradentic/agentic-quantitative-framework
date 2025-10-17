"""Unit tests for drift monitoring helpers."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # pragma: no branch - deterministic in tests
    sys.path.insert(0, str(ROOT))

from monitoring import drift_monitor


class _DummyTable:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def insert(self, payload):  # type: ignore[no-untyped-def]
        self.rows.append(payload)
        return self

    def execute(self):  # type: ignore[no-untyped-def]
        return types.SimpleNamespace(data=list(self.rows))


class _DummySupabase:
    def __init__(self) -> None:
        self.tables: dict[str, _DummyTable] = {}

    def table(self, name: str) -> _DummyTable:
        table = self.tables.get(name)
        if table is None:
            table = _DummyTable()
            self.tables[name] = table
        return table


def test_sharpe_threshold_logs_drift_event(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DummySupabase()
    monkeypatch.setattr(drift_monitor, "get_supabase_client", lambda: client)

    summary = {"sharpe_ratio": 0.2, "roc_auc": 0.71}
    thresholds = drift_monitor.DriftThresholds(min_sharpe=0.5)
    evaluation = drift_monitor.evaluate_drift(summary, thresholds=thresholds)

    assert evaluation.triggered
    drift_monitor.handle_drift(
        evaluation,
        strategy_id="demo_strategy",
        metadata={"run_id": "abc123"},
        logger=None,
    )

    table = client.tables.get("drift_events")
    assert table is not None
    assert len(table.rows) == 1
    event = table.rows[0]
    assert event["metric"] == "sharpe_ratio"
    details = event["details"]
    assert isinstance(details, dict)
    assert details["metric_value"] == pytest.approx(0.2)
    assert details["threshold"] == pytest.approx(0.5)
    assert details["metadata"]["run_id"] == "abc123"
    assert details["summary"]["sharpe_ratio"] == pytest.approx(0.2)


def test_no_event_logged_when_above_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DummySupabase()
    monkeypatch.setattr(drift_monitor, "get_supabase_client", lambda: client)

    summary = {"sharpe_ratio": 0.8}
    thresholds = drift_monitor.DriftThresholds(min_sharpe=0.5)
    evaluation = drift_monitor.evaluate_drift(summary, thresholds=thresholds)

    assert not evaluation.triggered
    drift_monitor.handle_drift(
        evaluation,
        strategy_id="demo_strategy",
        metadata={"run_id": "abc123"},
        logger=None,
    )

    assert "drift_events" not in client.tables
