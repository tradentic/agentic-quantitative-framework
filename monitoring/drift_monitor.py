"""Utilities for summarising backtests and monitoring metric drift."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import os
from typing import Any, Mapping, Protocol, Sequence

from framework.supabase_client import (
    MissingSupabaseConfiguration,
    get_supabase_client,
    insert_backtest_result,
)


class _SupportsMetrics(Protocol):
    """Protocol describing objects that expose a ``metrics`` mapping."""

    metrics: Mapping[str, Any]


def _env_float(name: str, default: float | None) -> float | None:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(slots=True)
class DriftThresholds:
    """Metric floors that signal drift when breached."""

    min_sharpe: float | None = None
    metric_floors: dict[str, float] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "DriftThresholds":
        """Return thresholds derived from the process environment."""

        return cls(
            min_sharpe=_env_float("DRIFT_MIN_SHARPE", 0.5),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_sharpe": self.min_sharpe,
            "metric_floors": dict(self.metric_floors),
        }


@dataclass(slots=True)
class DriftEvaluation:
    """Result of comparing metric summaries against thresholds."""

    summary: dict[str, float]
    thresholds: DriftThresholds
    triggered_metrics: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def triggered(self) -> bool:
        return bool(self.triggered_metrics)


class DriftDetected(RuntimeError):
    """Raised when callers request hard signalling on drift detection."""

    def __init__(self, evaluation: DriftEvaluation) -> None:
        super().__init__("Metric drift detected")
        self.evaluation = evaluation


def summarize_evaluation_metrics(
    results: Sequence[_SupportsMetrics | Mapping[str, Any]]
) -> dict[str, float]:
    """Collapse evaluation results into a flat mapping of numeric metrics."""

    summary: dict[str, float] = {}
    for result in results:
        metrics: Mapping[str, Any] | None
        if isinstance(result, Mapping):
            metrics = result.get("metrics") if "metrics" in result else None
        else:
            metrics = getattr(result, "metrics", None)
        if not isinstance(metrics, Mapping):
            continue
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                summary[key] = float(value)
    return summary


def _extract_sharpe(summary: Mapping[str, Any]) -> float | None:
    for candidate in ("sharpe_ratio", "sharpe", "sharpe_estimate"):
        value = summary.get(candidate)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def evaluate_drift(
    summary: Mapping[str, Any],
    *,
    thresholds: DriftThresholds | None = None,
) -> DriftEvaluation:
    """Compare metric summary against thresholds to determine drift."""

    thresholds = thresholds or DriftThresholds.default()
    triggered: dict[str, dict[str, float]] = {}

    sharpe_threshold = thresholds.min_sharpe
    sharpe_value = _extract_sharpe(summary)
    if sharpe_threshold is not None and sharpe_value is not None:
        if sharpe_value < sharpe_threshold:
            triggered["sharpe_ratio"] = {
                "value": sharpe_value,
                "threshold": sharpe_threshold,
            }

    for metric, floor in thresholds.metric_floors.items():
        value = summary.get(metric)
        if isinstance(value, (int, float)) and value < floor:
            triggered[metric] = {
                "value": float(value),
                "threshold": float(floor),
            }

    return DriftEvaluation(
        summary=dict((k, float(v)) for k, v in summary.items() if isinstance(v, (int, float))),
        thresholds=thresholds,
        triggered_metrics=triggered,
    )


def log_backtest_metrics(
    summary: Mapping[str, Any],
    *,
    strategy_id: str,
    config: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any] | None:
    """Persist key metrics into Supabase for longitudinal monitoring."""

    payload = {
        "strategy_id": strategy_id,
        "config": dict(config or {}),
        "metrics": {k: float(v) for k, v in summary.items() if isinstance(v, (int, float))},
        "artifacts": dict(artifacts or {}),
    }
    try:
        return insert_backtest_result(payload)
    except MissingSupabaseConfiguration:
        if logger:
            logger.debug(
                "Supabase not configured; skipping metric logging for strategy %s",
                strategy_id,
            )
        return None
    except Exception as exc:  # pragma: no cover - defensive guard
        if logger:
            logger.warning(
                "Failed to persist backtest metrics for strategy %s: %s",
                strategy_id,
                exc,
            )
        return None


def record_drift_event(
    evaluation: DriftEvaluation,
    *,
    strategy_id: str,
    trigger_type: str = "metric_threshold",
    metadata: Mapping[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> list[dict[str, Any]]:
    """Insert drift events into Supabase for the triggered metrics."""

    if not evaluation.triggered:
        return []

    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        if logger:
            logger.debug(
                "Supabase not configured; skipping drift event logging for %s",
                strategy_id,
            )
        return []

    now = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    details_common: dict[str, Any] = {
        "strategy_id": strategy_id,
        "summary": evaluation.summary,
        "thresholds": evaluation.thresholds.to_dict(),
    }
    if metadata:
        details_common["metadata"] = dict(metadata)

    records: list[dict[str, Any]] = []
    for metric, data in evaluation.triggered_metrics.items():
        details = dict(details_common)
        details.update(
            {
                "metric_value": data["value"],
                "threshold": data["threshold"],
            }
        )
        payload = {
            "metric": metric,
            "trigger_type": trigger_type,
            "triggered_at": now,
            "details": details,
        }
        try:
            response = client.table("drift_events").insert(payload).execute()
        except Exception as exc:  # pragma: no cover - network failure guard
            if logger:
                logger.warning(
                    "Failed to log drift event for %s on strategy %s: %s",
                    metric,
                    strategy_id,
                    exc,
                )
            continue
        data_payload = getattr(response, "data", None)
        if isinstance(data_payload, list) and data_payload:
            records.append(data_payload[0])
        else:
            records.append(payload)
    return records


def handle_drift(
    evaluation: DriftEvaluation,
    *,
    strategy_id: str,
    trigger_type: str = "metric_threshold",
    metadata: Mapping[str, Any] | None = None,
    logger: logging.Logger | None = None,
    raise_on_trigger: bool = False,
) -> DriftEvaluation:
    """Persist drift events and optionally raise a retraining signal."""

    if not evaluation.triggered:
        return evaluation

    record_drift_event(
        evaluation,
        strategy_id=strategy_id,
        trigger_type=trigger_type,
        metadata=metadata,
        logger=logger,
    )

    if raise_on_trigger:
        raise DriftDetected(evaluation)

    if logger:
        logger.warning(
            "Metric drift detected for %s; triggered metrics: %s",
            strategy_id,
            evaluation.triggered_metrics,
        )
    return evaluation


__all__ = [
    "DriftDetected",
    "DriftEvaluation",
    "DriftThresholds",
    "evaluate_drift",
    "handle_drift",
    "log_backtest_metrics",
    "record_drift_event",
    "summarize_evaluation_metrics",
]
