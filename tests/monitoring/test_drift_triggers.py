"""Unit tests for monitoring.drift_monitor drift detection utilities."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

drift_monitor = importlib.import_module("monitoring.drift_monitor")
from monitoring.drift_monitor import DriftThreshold, RetrainingRequired, assess_metric_drift


def test_sharpe_threshold_triggers_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sharpe ratios below the configured minimum should raise retraining signals."""

    recorded: list = []

    def _fake_insert(record: drift_monitor.DriftEventRecord) -> dict[str, str]:
        recorded.append(record)
        return {"metric": record.metric, "trigger_type": record.trigger_type}

    monkeypatch.setattr(drift_monitor, "insert_drift_event", _fake_insert)

    threshold = DriftThreshold(metric="sharpe", min_value=1.2, trigger_type="sharpe_floor")
    artefact = {"summary": {"sharpe": 0.85}}

    with pytest.raises(RetrainingRequired) as exc:
        assess_metric_drift(artefact, [threshold], context={"strategy_id": "demo"})

    assert len(recorded) == 1
    assert recorded[0].metric == "sharpe"
    assert recorded[0].details["minimum"] == pytest.approx(1.2)
    assert exc.value.events[0].metric == "sharpe"
    assert exc.value.events[0].details["observed"] == pytest.approx(0.85)


def test_metrics_above_threshold_do_not_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """When metrics exceed the threshold no drift events should be recorded."""

    recorded: list = []

    def _fake_insert(record: drift_monitor.DriftEventRecord) -> dict[str, str]:
        recorded.append(record)
        return {"metric": record.metric}

    monkeypatch.setattr(drift_monitor, "insert_drift_event", _fake_insert)

    threshold = DriftThreshold(metric="sharpe", min_value=0.4)
    artefact = {"summary": {"sharpe": 0.75}}

    events = assess_metric_drift(artefact, [threshold], context={"strategy_id": "demo"})

    assert events == []
    assert recorded == []
