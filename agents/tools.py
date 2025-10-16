"""Supabase-backed tools that power the LangGraph agent chain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable

from framework.supabase_client import build_metadata, get_supabase_client


def propose_new_feature(feature_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a feature proposal to Supabase for downstream review."""

    client = get_supabase_client()
    record = {
        "name": feature_payload.get("name"),
        "description": feature_payload.get("description"),
        "status": feature_payload.get("status", "proposed"),
        "metadata": build_metadata(feature_payload.get("metadata")),
        "created_at": feature_payload.get("created_at") or datetime.utcnow().isoformat(),
    }
    response = client.table("feature_proposals").insert(record).execute()
    data = response.data if hasattr(response, "data") else None
    return {
        "action": "propose_new_feature",
        "record": data[0] if data else record,
    }


def run_backtest(backtest_config: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger a Supabase RPC that executes a backtest for the active strategy."""

    client = get_supabase_client()
    rpc_payload = {
        "strategy_id": backtest_config.get("strategy_id"),
        "window_start": backtest_config.get("window_start"),
        "window_end": backtest_config.get("window_end"),
        "parameters": backtest_config.get("parameters", {}),
    }
    response = client.rpc("run_strategy_backtest", rpc_payload).execute()
    data = response.data if hasattr(response, "data") else None
    return {
        "action": "run_backtest",
        "result": data or {"submitted": True, "rpc_payload": rpc_payload},
    }


def prune_vectors(filter_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call into Supabase to remove stale embeddings from pgvector storage."""

    client = get_supabase_client()
    rpc_payload = {
        "stale_before": filter_payload.get("stale_before"),
        "max_similarity": filter_payload.get("max_similarity"),
        "asset_universe": filter_payload.get("asset_universe"),
    }
    response = client.rpc("prune_signal_embeddings", rpc_payload).execute()
    data = response.data if hasattr(response, "data") else None
    return {
        "action": "prune_vectors",
        "result": data or {"submitted": True, "rpc_payload": rpc_payload},
    }


def refresh_vector_store(refresh_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule a Supabase job to regenerate embeddings and refresh similarity indexes."""

    client = get_supabase_client()
    rpc_payload = {
        "asset_ids": refresh_payload.get("asset_ids"),
        "window_start": refresh_payload.get("window_start"),
        "window_end": refresh_payload.get("window_end"),
        "backfill": refresh_payload.get("backfill", False),
    }
    response = client.rpc("refresh_signal_embeddings", rpc_payload).execute()
    data = response.data if hasattr(response, "data") else None
    return {
        "action": "refresh_vector_store",
        "result": data or {"submitted": True, "rpc_payload": rpc_payload},
    }


def batch_upsert_embeddings(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Helper to upsert raw embedding vectors into Supabase."""

    client = get_supabase_client()
    payload = list(records)
    response = client.table("signal_embeddings").upsert(payload).execute()
    data = response.data if hasattr(response, "data") else None
    return {
        "action": "batch_upsert_embeddings",
        "result": data or {"submitted": True, "rowcount": len(payload)},
    }
