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
    list_pending_embedding_jobs,
    record_feature,
    store_artifact_file,
    store_artifact_json,
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
    registry_rows = record_feature(entry)

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


__all__ = [
    "poll_embedding_jobs",
    "propose_new_feature",
    "prune_vectors",
    "refresh_vector_store",
    "run_backtest",
]
