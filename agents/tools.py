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
    get_supabase_client,
    insert_backtest_result,
    insert_embeddings,
    insert_feature,
    list_pending_embedding_jobs,
    store_artifact_file,
    store_artifact_json,
)
from monitoring import (
    DriftThreshold,
    RetrainingRequired,
    assess_metric_drift,
    load_recent_backtests,
)

FEATURES_DIR = Path(__file__).resolve().parent.parent / "features"
ARTIFACT_ROOT = Path("artifacts")


def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
    return cleaned.lower() or "feature"


def _ensure_features_dir() -> None:
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)


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

    code = feature_payload["code"].rstrip() + "\n"
    feature_path.write_text(code, encoding="utf-8")

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

    result = execute_backtest(backtest_config)
    summary = result.get("summary", {})
    equity_curve = result.get("equity_curve", [])

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    strategy = backtest_config["strategy_id"]
    artifact_dir = ARTIFACT_ROOT / "backtests" / strategy / timestamp
    artifact_dir.mkdir(parents=True, exist_ok=True)

    summary_key = f"backtests/{strategy}/{timestamp}/summary.json"
    plot_path = artifact_dir / "equity_curve.png"
    _render_equity_curve(equity_curve, title=f"{strategy} Equity Curve", output_path=plot_path)

    storage_summary_path = store_artifact_json(summary_key, summary)
    storage_plot_path = store_artifact_file(
        f"backtests/{strategy}/{timestamp}/equity_curve.png",
        str(plot_path),
    )

    artifacts = {
        "summary": storage_summary_path,
        "plot": storage_plot_path,
    }

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

    client = get_supabase_client()
    payload = {
        "max_age_days": filter_payload.get("max_age_days", 90),
        "min_t_stat": filter_payload.get("min_t_stat", 0.5),
        "regime_diversity": filter_payload.get("regime_diversity", 3),
        "asset_universe": filter_payload.get("asset_universe"),
    }
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

    timestamps = [datetime.fromisoformat(window["timestamp"]) for window in windows]
    values = np.asarray([window["values"] for window in windows], dtype=float)
    metadata = refresh_payload.get("metadata", {})

    records = generate_ts2vec_features(
        timestamps=timestamps,
        values=values,
        asset_symbol=asset_symbol,
        metadata=metadata,
    )
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

    return list_pending_embedding_jobs(limit=limit)


def _coerce_threshold(entry: dict[str, Any]) -> DriftThreshold:
    metric = entry.get("metric")
    if not metric:
        raise ValueError("Each threshold entry must include a metric name.")
    min_value = entry.get("min_value")
    max_value = entry.get("max_value")
    return DriftThreshold(
        metric=metric,
        min_value=float(min_value) if min_value is not None else None,
        max_value=float(max_value) if max_value is not None else None,
        trigger_type=entry.get("trigger_type", "threshold"),
        retrain_on_trigger=bool(entry.get("retrain_on_trigger", True)),
    )


def detect_drift_and_retrain(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate stored backtest metrics and trigger retraining if thresholds breach."""

    strategy_id = payload.get("strategy_id")
    if not strategy_id:
        raise ValueError("`strategy_id` is required to detect drift.")

    lookback = int(payload.get("lookback", 5))
    thresholds_config = payload.get("thresholds") or []
    thresholds: list[DriftThreshold] = []
    for entry in thresholds_config:
        thresholds.append(_coerce_threshold(entry))

    if not thresholds:
        minimum = payload.get("sharpe_min")
        minimum = float(minimum) if minimum is not None else 1.0
        thresholds = [
            DriftThreshold(
                metric="sharpe",
                min_value=minimum,
                trigger_type="sharpe_floor",
                retrain_on_trigger=True,
            )
        ]

    records = load_recent_backtests(strategy_id=strategy_id, limit=lookback)
    if not records:
        return {
            "action": "detect_drift_and_retrain",
            "strategy_id": strategy_id,
            "status": "no_data",
        }

    latest = records[0]
    artefact = {"metrics": latest.get("metrics", {})}
    context = {
        "strategy_id": strategy_id,
        "backtest_id": str(latest.get("id")),
        "source": "langgraph.detect_drift_and_retrain",
    }

    try:
        assess_metric_drift(artefact, thresholds, context=context)
    except RetrainingRequired as exc:
        return {
            "action": "detect_drift_and_retrain",
            "strategy_id": strategy_id,
            "status": "retraining_triggered",
            "events": [
                {
                    "metric": event.metric,
                    "observed": event.observed,
                    "trigger_type": event.trigger_type,
                    "details": event.details,
                }
                for event in exc.events
            ],
        }

    return {
        "action": "detect_drift_and_retrain",
        "strategy_id": strategy_id,
        "status": "no_drift",
        "checked_at": datetime.utcnow().isoformat(),
    }


__all__ = [
    "poll_embedding_jobs",
    "propose_new_feature",
    "prune_vectors",
    "refresh_vector_store",
    "run_backtest",
    "detect_drift_and_retrain",
]
