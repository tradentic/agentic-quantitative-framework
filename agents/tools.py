"""Supabase-backed tools that power the LangGraph agent chain."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from backtest.engine import run_backtest as execute_backtest
from features.generate_ts2vec_embeddings import generate_ts2vec_features
from framework.supabase_client import (
    BacktestResult,
    FeatureRegistryEntry,
    MissingSupabaseConfiguration,
    get_supabase_client,
    insert_backtest_result,
    insert_embeddings,
    insert_feature,
    list_pending_embedding_jobs,
    store_artifact_file,
    store_artifact_json,
)
from monitoring.drift_monitor import DriftThresholds, evaluate_drift, handle_drift
from observability.otel import init_tracing

FEATURES_DIR = Path(__file__).resolve().parent.parent / "features"
ARTIFACT_ROOT = Path("artifacts")


tracer = init_tracing("langgraph-tools")


def _tool_span(name: str, **attributes: Any):
    payload = {key: value for key, value in attributes.items() if value is not None}
    return tracer.start_as_current_span(f"agent_tool:{name}", attributes=payload)


def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
    return cleaned.lower() or "feature"


def _ensure_features_dir() -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)


def _coerce_optional_float(value: Any, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_metric_floors(raw: Any) -> dict[str, float]:
    floors: dict[str, float] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                floors[str(key)] = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
    return floors


def propose_new_feature(feature_payload: dict[str, Any]) -> dict[str, Any]:
    """Create or update a feature module and record metadata in Supabase."""

    required_fields = {"name", "code"}
    if missing := required_fields.difference(feature_payload):
        raise ValueError(f"Missing required fields for feature proposal: {sorted(missing)}")

    _ensure_features_dir()

    name = feature_payload["name"]
    version = feature_payload.get("version") or datetime.utcnow().strftime("%Y%m%d%H%M%S")
    slug = feature_payload.get("slug") or _slugify(name)
    filename = feature_payload.get("filename") or f"{slug}_{version}.py"
    feature_path = FEATURES_DIR / filename

    if feature_path.exists() and not feature_payload.get("allow_overwrite", False):
        raise FileExistsError(f"Feature file already exists: {feature_path}")

    with _tool_span(
        "propose_new_feature", feature_name=name, version=version, file_name=filename
    ) as span:
        code = feature_payload["code"].rstrip() + "\n"
        feature_path.write_text(code, encoding="utf-8")
        span.set_attribute("file_path", str(feature_path))

        metadata = feature_payload.get("metadata", {})
        metadata.setdefault("created_at", datetime.utcnow().isoformat())
        entry = FeatureRegistryEntry(
            name=name,
            version=version,
            path=str(feature_path.relative_to(Path.cwd())),
            description=feature_payload.get("description", ""),
            status=feature_payload.get("status", "proposed"),
            meta=metadata,
        )
        registry_rows = insert_feature(entry)

        registry_entry = (
            registry_rows[0] if isinstance(registry_rows, list) and registry_rows else registry_rows
        )
        span.set_attribute("supabase_rows", 1 if registry_entry else 0)

        return {
            "action": "propose_new_feature",
            "file_path": str(feature_path),
            "registry_entry": registry_entry,
        }


def _render_equity_curve(equity_curve: Iterable[float], *, title: str, output_path: Path) -> Path:
    values = list(equity_curve)
    if not values:
        return output_path
    plt.figure(figsize=(8, 4))
    plt.plot(range(len(values)), values, color="#4f46e5")
    plt.title(title)
    plt.xlabel("Step")
    plt.ylabel("Equity")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    return output_path


def run_backtest(backtest_config: dict[str, Any]) -> dict[str, Any]:
    """Execute a local backtest, persist artifacts, and register the result."""

    if "strategy_id" not in backtest_config:
        raise ValueError("`strategy_id` is required for backtests.")

    strategy = backtest_config["strategy_id"]
    with _tool_span("run_backtest", strategy_id=strategy) as span:
        result = execute_backtest(backtest_config)
        summary = result.get("summary", {})
        equity_curve = result.get("equity_curve", [])

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        artifact_dir = ARTIFACT_ROOT / "backtests" / strategy / timestamp
        artifact_dir.mkdir(parents=True, exist_ok=True)
        span.set_attribute("artifact_dir", str(artifact_dir))

        summary_key = f"backtests/{strategy}/{timestamp}/summary.json"
        plot_path = artifact_dir / "equity_curve.png"
        _render_equity_curve(
            equity_curve, title=f"{strategy} Equity Curve", output_path=plot_path
        )

        storage_summary_path = store_artifact_json(summary_key, summary)
        storage_plot_path = store_artifact_file(
            f"backtests/{strategy}/{timestamp}/equity_curve.png",
            str(plot_path),
        )

        artifacts = {
            "summary": storage_summary_path,
            "plot": storage_plot_path,
        }
        span.set_attribute("artifacts_stored", len(artifacts))
        if summary.get("sharpe") is not None:
            span.set_attribute("sharpe", summary.get("sharpe"))

        backtest_record = BacktestResult(
            strategy_id=strategy,
            config=backtest_config,
            metrics=summary,
            artifacts=artifacts,
        )
        insert_backtest_result(backtest_record)

        return {
            "action": "run_backtest",
            "result": summary,
            "artifacts": artifacts,
        }


def prune_vectors(filter_payload: dict[str, Any]) -> dict[str, Any]:
    """Call the Supabase RPC that archives stale embeddings."""

    with _tool_span("prune_vectors") as span:
        client = get_supabase_client()
        payload = {
            "max_age_days": filter_payload.get("max_age_days", 90),
            "min_t_stat": filter_payload.get("min_t_stat", 0.5),
            "regime_diversity": filter_payload.get("regime_diversity", 3),
            "asset_universe": filter_payload.get("asset_universe"),
        }
        span.set_attribute("max_age_days", payload["max_age_days"])
        span.set_attribute("min_t_stat", payload["min_t_stat"])
        response = client.rpc("rpc_prune_vectors", payload).execute()
        data = getattr(response, "data", {})
        return {
            "action": "prune_vectors",
            "result": data or {"submitted": True, "criteria": payload},
        }


def refresh_vector_store(refresh_payload: dict[str, Any]) -> dict[str, Any]:
    """Regenerate embeddings and refresh pgvector storage."""

    asset_symbol = refresh_payload.get("asset_symbol")
    windows = refresh_payload.get("windows") or []
    if not asset_symbol or not windows:
        raise ValueError(
            "`asset_symbol` and `windows` are required for refreshing embeddings."
        )

    with _tool_span(
        "refresh_vector_store",
        asset_symbol=asset_symbol,
        window_count=len(windows),
    ) as span:
        timestamps = [datetime.fromisoformat(window["timestamp"]) for window in windows]
        values = np.asarray([window["values"] for window in windows], dtype=float)
        metadata = refresh_payload.get("metadata", {})

        records = generate_ts2vec_features(
            timestamps=timestamps,
            values=values,
            asset_symbol=asset_symbol,
            metadata=metadata,
        )
        span.set_attribute("record_count", len(records))
        insert_embeddings(records)

        return {
            "action": "refresh_vector_store",
            "result": {
                "asset_symbol": asset_symbol,
                "rows": len(records),
            },
        }


def poll_embedding_jobs(limit: int = 5) -> list[dict[str, Any]]:
    """Expose embedding jobs to Prefect flows and ad-hoc tooling."""

    with _tool_span("poll_embedding_jobs", limit=limit) as span:
        jobs = list_pending_embedding_jobs(limit=limit)
        span.set_attribute("job_count", len(jobs))
        return jobs


def propose_feature_from_persistence(idea_payload: dict[str, Any]) -> dict[str, Any]:
    """Record persistence-derived feature ideas in Supabase."""

    required_fields = {"name", "insight"}
    if missing := required_fields.difference(idea_payload):
        raise ValueError(f"Missing required fields for persistence feature proposal: {sorted(missing)}")

    metadata = idea_payload.get("metadata", {})
    record = {
        "name": idea_payload["name"],
        "insight": idea_payload["insight"],
        "source": idea_payload.get("source", "tda_persistence"),
        "created_at": datetime.utcnow().isoformat(),
        "metadata": metadata,
    }

    with _tool_span("propose_feature_from_persistence", feature_name=record["name"]) as span:
        try:
            client = get_supabase_client()
        except MissingSupabaseConfiguration:
            span.set_attribute("persisted", False)
            return {
                "action": "propose_feature_from_persistence",
                "record": record,
                "persisted": False,
                "reason": "Supabase not configured",
            }

        response = client.table("feature_ideas").insert(record).execute()
        data = getattr(response, "data", None)
        persisted = isinstance(data, list) and bool(data)
        span.set_attribute("persisted", persisted)
        return {
            "action": "propose_feature_from_persistence",
            "record": data[0] if persisted else record,
            "persisted": persisted,
        }


def detect_drift_and_retrain(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inspect stored backtest metrics and trigger retraining when drift emerges."""

    payload = payload or {}
    strategy_id = payload.get("strategy_id")
    if not strategy_id:
        raise ValueError("`strategy_id` is required for drift detection.")

    with _tool_span("detect_drift_and_retrain", strategy_id=strategy_id) as span:
        default_thresholds = DriftThresholds.default()
        min_sharpe = _coerce_optional_float(
            payload.get("min_sharpe"), default_thresholds.min_sharpe
        )
        metric_floors = _coerce_metric_floors(payload.get("metric_floors"))
        thresholds = DriftThresholds(min_sharpe=min_sharpe, metric_floors=metric_floors)

        try:
            lookback = int(payload.get("lookback", 5))
        except (TypeError, ValueError):
            lookback = 5
        lookback = max(1, lookback)
        span.set_attribute("lookback", lookback)
        stop_on_first = bool(payload.get("stop_on_first", True))
        raise_on_trigger = bool(payload.get("raise_on_trigger", False))
        metadata = payload.get("metadata")
        metadata_dict = metadata if isinstance(metadata, dict) else {}

        try:
            client = get_supabase_client()
        except MissingSupabaseConfiguration:
            span.set_attribute("supabase_available", False)
            return {
                "action": "detect_drift_and_retrain",
                "strategy_id": strategy_id,
                "retrain": False,
                "reason": "Supabase not configured",
                "evaluations": [],
                "thresholds": thresholds.to_dict(),
                "checked": 0,
            }

        span.set_attribute("supabase_available", True)
        try:
            response = (
                client.table("backtest_results")
                .select("metrics, config, created_at")
                .eq("strategy_id", strategy_id)
                .order("created_at", desc=True)
                .limit(lookback)
                .execute()
            )
            rows = getattr(response, "data", []) or []
        except Exception as exc:  # pragma: no cover - network failure guard
            span.set_attribute("fetch_error", True)
            return {
                "action": "detect_drift_and_retrain",
                "strategy_id": strategy_id,
                "retrain": False,
                "reason": f"Failed to fetch metrics: {exc}",
                "evaluations": [],
                "thresholds": thresholds.to_dict(),
                "checked": 0,
            }

        evaluations: list[dict[str, Any]] = []
        triggered = False
        span.set_attribute("checked", len(rows))

        for row in rows:
            metrics = row.get("metrics") or {}
            evaluation = evaluate_drift(metrics, thresholds=thresholds)
            if evaluation.triggered:
                triggered = True
                context_meta = dict(metadata_dict)
                context_meta.setdefault("source", "detect_drift_and_retrain")
                context_meta["backtest_created_at"] = row.get("created_at")
                handle_drift(
                    evaluation,
                    strategy_id=strategy_id,
                    metadata=context_meta,
                    raise_on_trigger=raise_on_trigger,
                )
                evaluations.append(
                    {
                        "created_at": row.get("created_at"),
                        "triggered_metrics": evaluation.triggered_metrics,
                        "summary": evaluation.summary,
                    }
                )
                if stop_on_first:
                    break

        span.set_attribute("triggered", triggered)
        return {
            "action": "detect_drift_and_retrain",
            "strategy_id": strategy_id,
            "retrain": triggered,
            "evaluations": evaluations,
            "thresholds": thresholds.to_dict(),
            "checked": len(rows),
        }


__all__ = [
    "poll_embedding_jobs",
    "propose_feature_from_persistence",
    "propose_new_feature",
    "prune_vectors",
    "refresh_vector_store",
    "run_backtest",
    "detect_drift_and_retrain",
]
