"""Typed Supabase helpers shared across the Agentic Quantitative Framework."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import lru_cache
from importlib import import_module, util
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

ENV_URL_KEYS = ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
ENV_KEY_KEYS = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
)

DEFAULT_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "model-artifacts")


class MissingSupabaseConfiguration(RuntimeError):
    """Raised when the required Supabase environment variables are missing."""


def _load_supabase_client_factory() -> Any:
    """Dynamically import and return the Supabase client's factory function."""

    if util.find_spec("supabase") is None:
        raise ModuleNotFoundError(
            "The `supabase` Python client is required. Install it with `pip install supabase`.",
        )
    module = import_module("supabase")
    create_client = getattr(module, "create_client", None)
    if create_client is None:
        raise AttributeError("The Supabase client module does not expose `create_client`.")
    return create_client


def _resolve_env_value(candidates: Sequence[str]) -> str | None:
    for key in candidates:
        value = os.getenv(key)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def get_supabase_client() -> Any:
    """Return a cached Supabase client instance configured from the environment."""

    url = _resolve_env_value(ENV_URL_KEYS)
    key = _resolve_env_value(ENV_KEY_KEYS)
    if not url or not key:
        raise MissingSupabaseConfiguration(
            "Supabase credentials are not configured. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the environment."
        )
    factory = _load_supabase_client_factory()
    return factory(url, key)


def build_metadata(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Coerce optional metadata dictionaries into a Supabase-friendly payload."""

    return metadata.copy() if metadata else {}


class EmbeddingRecord(BaseModel):
    """Typed payload describing a pgvector embedding row."""

    id: UUID = Field(default_factory=uuid4)
    asset_symbol: str
    time_range: str | tuple[str, str] | tuple[datetime, datetime]
    embedding: list[float]
    regime_tag: str | None = None
    label: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)

    @validator("embedding")
    def _validate_dimensions(cls, value: list[float]) -> list[float]:
        if len(value) != 128:
            raise ValueError("Embeddings must contain 128 dimensions for pgvector(128).")
        return value

    @validator("time_range", pre=True)
    def _coerce_time_range(
        cls, value: str | tuple[str, str] | tuple[datetime, datetime]
    ) -> str:
        if isinstance(value, str):
            return value
        start, end = value
        if isinstance(start, datetime):
            start = start.isoformat()
        if isinstance(end, datetime):
            end = end.isoformat()
        return f"[{start},{end})"


class BacktestResult(BaseModel):
    """Persisted backtest summary for analytics and auditability."""

    id: UUID = Field(default_factory=uuid4)
    strategy_id: str
    run_at: datetime = Field(default_factory=datetime.utcnow)
    config: dict[str, Any]
    metrics: dict[str, Any]
    artifacts_path: str | None = None


@dataclass
class FeatureRegistryEntry:
    """Structured representation for entries in the feature registry."""

    feature_id: UUID = field(default_factory=uuid4)
    name: str = ""
    version: str = ""
    file_path: str = ""
    description: str = ""
    status: str = "proposed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["feature_id"] = str(self.feature_id)
        return payload


def insert_embeddings(records: Sequence[EmbeddingRecord | dict[str, Any]]) -> list[dict[str, Any]]:
    """Bulk upsert embeddings into the `signal_embeddings` table."""

    client = get_supabase_client()
    payload: list[dict[str, Any]] = []
    for record in records:
        model = record if isinstance(record, EmbeddingRecord) else EmbeddingRecord(**record)
        serialized = model.dict()
        serialized["id"] = str(serialized["id"])
        payload.append(serialized)
    response = client.table("signal_embeddings").upsert(payload).execute()
    return getattr(response, "data", payload)


def fetch_nearest(
    query_embedding: Sequence[float],
    *,
    match_count: int = 5,
    filter_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Query the closest vectors using the `match_signal_embeddings` RPC."""

    client = get_supabase_client()
    payload = {
        "query_embedding": list(query_embedding),
        "match_count": match_count,
        "filter": filter_params or {},
    }
    response = client.rpc("match_signal_embeddings", payload).execute()
    return getattr(response, "data", [])


def insert_backtest_result(result: BacktestResult | dict[str, Any]) -> dict[str, Any]:
    """Insert a backtest result row into Supabase."""

    model = result if isinstance(result, BacktestResult) else BacktestResult(**result)
    payload = model.dict()
    payload["id"] = str(payload["id"])
    payload["run_at"] = payload["run_at"].isoformat()
    client = get_supabase_client()
    response = client.table("backtest_results").insert(payload).execute()
    return getattr(response, "data", payload)


def list_failed_features(limit: int = 25) -> list[dict[str, Any]]:
    """Return feature registry rows marked as failed for quick triage."""

    client = get_supabase_client()
    response = (
        client.table("feature_registry")
        .select("*")
        .eq("status", "failed")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return getattr(response, "data", [])


def record_feature(
    entry: FeatureRegistryEntry | dict[str, Any],
) -> list[dict[str, Any]] | dict[str, Any]:
    """Insert or update a feature registry entry in Supabase."""

    payload = entry.as_dict() if isinstance(entry, FeatureRegistryEntry) else entry
    client = get_supabase_client()
    response = client.table("feature_registry").upsert(payload).execute()
    result = getattr(response, "data", payload)
    return cast(list[dict[str, Any]] | dict[str, Any], result)


def store_artifact_json(path: str, content: dict[str, Any], *, bucket: str | None = None) -> str:
    """Upload JSON content to Supabase Storage and return the object path."""

    bucket_name = bucket or DEFAULT_STORAGE_BUCKET
    client = get_supabase_client()
    storage = client.storage()
    bucket_client = storage.from_(bucket_name)
    payload = json.dumps(content, separators=(",", ":")).encode("utf-8")
    bucket_client.upload(path, payload, {"content-type": "application/json", "upsert": "true"})
    return f"{bucket_name}/{path}"


def store_artifact_file(path: str, file_path: str, *, bucket: str | None = None) -> str:
    """Upload a local file to Supabase Storage and return the object path."""

    bucket_name = bucket or DEFAULT_STORAGE_BUCKET
    client = get_supabase_client()
    storage = client.storage()
    bucket_client = storage.from_(bucket_name)
    with open(file_path, "rb") as fh:
        bucket_client.upload(
            path,
            fh,
            {"content-type": "application/octet-stream", "upsert": "true"},
        )
    return f"{bucket_name}/{path}"


def fetch_agent_state(agent_id: str) -> dict[str, Any]:
    """Load serialized agent state from Supabase."""

    client = get_supabase_client()
    response = (
        client.table("agent_state")
        .select("state")
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
    )
    data = getattr(response, "data", [])
    if not data:
        return {}
    return data[0].get("state") or {}


def persist_agent_state(agent_id: str, state: dict[str, Any]) -> None:
    """Persist serialized agent state back to Supabase."""

    client = get_supabase_client()
    payload = {"agent_id": agent_id, "state": state, "updated_at": datetime.utcnow().isoformat()}
    client.table("agent_state").upsert(payload, on_conflict="agent_id").execute()


def mark_embedding_job_complete(job_id: UUID | str) -> None:
    """Update an embedding job to completed in Supabase."""

    client = get_supabase_client()
    client.table("embedding_jobs").update({"status": "completed"}).eq("id", str(job_id)).execute()


def list_pending_embedding_jobs(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch pending embedding jobs awaiting processing."""

    client = get_supabase_client()
    response = (
        client.table("embedding_jobs")
        .select("*")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return getattr(response, "data", [])


__all__ = [
    "BacktestResult",
    "EmbeddingRecord",
    "FeatureRegistryEntry",
    "MissingSupabaseConfiguration",
    "build_metadata",
    "fetch_agent_state",
    "fetch_nearest",
    "get_supabase_client",
    "insert_backtest_result",
    "insert_embeddings",
    "list_failed_features",
    "list_pending_embedding_jobs",
    "mark_embedding_job_complete",
    "persist_agent_state",
    "record_feature",
    "store_artifact_file",
    "store_artifact_json",
]
