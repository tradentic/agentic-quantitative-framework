"""Utilities for detecting performance drift and triggering retraining workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from framework.supabase_client import (
    BacktestResult,
    DriftEventRecord,
    fetch_backtest_results,
    insert_backtest_result,
    insert_drift_event,
)

Number = float | int


@dataclass(slots=True)
class DriftThreshold:
    """Threshold configuration for a specific metric."""

    metric: str
    min_value: float | None = None
    max_value: float | None = None
    trigger_type: str = "threshold"
    retrain_on_trigger: bool = True


@dataclass(slots=True)
class MetricSummary:
    """Collected statistics for a metric extracted from artefacts."""

    metric: str
    values: list[float]

    @property
    def latest(self) -> float | None:
        return self.values[-1] if self.values else None

    @property
    def best(self) -> float | None:
        return max(self.values) if self.values else None

    @property
    def worst(self) -> float | None:
        return min(self.values) if self.values else None


@dataclass(slots=True)
class DriftEvent:
    """Context captured when a drift threshold triggers."""

    metric: str
    observed: float
    threshold: DriftThreshold
    trigger_type: str
    details: dict[str, Any]


class RetrainingRequired(RuntimeError):
    """Raised when drift thresholds signal that retraining must occur."""

    def __init__(self, events: Sequence[DriftEvent]):
        super().__init__(
            "Performance drift detected; retraining is required for one or more metrics."
        )
        self.events = list(events)


def _normalise_value(value: Number | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_metric_values(payload: Any, metric: str) -> list[float]:
    values: list[float] = []
    if isinstance(payload, Mapping):
        direct = _normalise_value(payload.get(metric))
        if direct is not None:
            values.append(direct)
        for key in ("metrics", "summary"):
            nested = payload.get(key)
            if nested is not None:
                values.extend(_collect_metric_values(nested, metric))
        models = payload.get("models")
        if isinstance(models, Sequence) and not isinstance(models, (str, bytes)):
            for model in models:
                values.extend(_collect_metric_values(model, metric))
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for item in payload:
            values.extend(_collect_metric_values(item, metric))
    return values


def extract_metric_summary(artefact: Mapping[str, Any] | Sequence[Any], metric: str) -> MetricSummary:
    """Extract numeric values for a metric from an artefact payload."""

    values = _collect_metric_values(artefact, metric)
    return MetricSummary(metric=metric, values=values)


def log_backtest_metrics(
    *,
    strategy_id: str,
    metrics: Mapping[str, Number],
    config: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a backtest snapshot in Supabase for downstream drift detection."""

    record = BacktestResult(
        strategy_id=strategy_id,
        config=dict(config or {}),
        metrics={key: float(value) for key, value in metrics.items()},
        artifacts=dict(artifacts or {}),
    )
    return insert_backtest_result(record)


def _build_event(
    *,
    summary: MetricSummary,
    threshold: DriftThreshold,
    observed: float,
    context: Mapping[str, Any] | None = None,
) -> DriftEvent:
    details = {
        "observed": observed,
        "minimum": threshold.min_value,
        "maximum": threshold.max_value,
    }
    if context:
        details["context"] = dict(context)
    return DriftEvent(
        metric=summary.metric,
        observed=observed,
        threshold=threshold,
        trigger_type=threshold.trigger_type,
        details=details,
    )


def log_drift_event(event: DriftEvent) -> dict[str, Any]:
    """Persist a drift event to Supabase."""

    payload = DriftEventRecord(
        metric=event.metric,
        trigger_type=event.trigger_type,
        triggered_at=datetime.now(timezone.utc),
        details=event.details,
    )
    return insert_drift_event(payload)


def assess_metric_drift(
    artefact: Mapping[str, Any] | Sequence[Any],
    thresholds: Iterable[DriftThreshold],
    *,
    context: Mapping[str, Any] | None = None,
    log_events: bool = True,
    raise_on_trigger: bool = True,
) -> list[DriftEvent]:
    """Evaluate thresholds and optionally log or raise when drift occurs."""

    triggered_events: list[DriftEvent] = []
    for threshold in thresholds:
        summary = extract_metric_summary(artefact, threshold.metric)
        observed = summary.latest
        if observed is None:
            continue
        if threshold.min_value is not None and observed < threshold.min_value:
            event = _build_event(
                summary=summary,
                threshold=threshold,
                observed=observed,
                context=context,
            )
            triggered_events.append(event)
        elif threshold.max_value is not None and observed > threshold.max_value:
            event = _build_event(
                summary=summary,
                threshold=threshold,
                observed=observed,
                context=context,
            )
            triggered_events.append(event)

    if log_events:
        for event in triggered_events:
            log_drift_event(event)

    actionable = [event for event in triggered_events if event.threshold.retrain_on_trigger]
    if actionable and raise_on_trigger:
        raise RetrainingRequired(actionable)

    return triggered_events


def load_recent_backtests(strategy_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Helper to expose recent backtest results from Supabase."""

    return fetch_backtest_results(strategy_id=strategy_id, limit=limit)


__all__ = [
    "DriftThreshold",
    "DriftEvent",
    "MetricSummary",
    "RetrainingRequired",
    "assess_metric_drift",
    "extract_metric_summary",
    "load_recent_backtests",
    "log_backtest_metrics",
    "log_drift_event",
]
