"""Typed Supabase helpers shared across the Agentic Quantitative Framework."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache, wraps
from importlib import import_module, util
from typing import Any, Callable, ParamSpec, TypeVar, cast  # noqa: UP035
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

ENV_URL_KEYS = ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
ENV_KEY_KEYS = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
)

DEFAULT_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "model-artifacts")
DEFAULT_RETRY_ATTEMPTS = int(os.getenv("SUPABASE_RETRY_ATTEMPTS", "3"))
DEFAULT_RETRY_BACKOFF = float(os.getenv("SUPABASE_RETRY_BACKOFF", "0.5"))


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


P = ParamSpec("P")
R = TypeVar("R")


def _retryable(*, attempts: int = DEFAULT_RETRY_ATTEMPTS, backoff: float = DEFAULT_RETRY_BACKOFF):
    """Simple exponential backoff retry decorator for Supabase RPCs."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            delay = backoff
            last_exception: Exception | None = None
            for attempt in range(1, max(attempts, 1) + 1):
                try:
                    return func(*args, **kwargs)
                except MissingSupabaseConfiguration:
                    raise
                except Exception as exc:  # pragma: no cover - defensive retry
                    last_exception = exc
                    if attempt >= max(attempts, 1):
                        raise
                    time.sleep(delay)
                    delay *= 2
            if last_exception is not None:  # pragma: no cover - guard
                raise last_exception
            raise RuntimeError("Retry wrapper exhausted without executing target function.")

        return wrapper

    return decorator


def build_metadata(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Coerce optional metadata dictionaries into a Supabase-friendly payload."""

    return metadata.copy() if metadata else {}


class EmbeddingRecord(BaseModel):
    """Typed payload describing a pgvector embedding row."""

    id: UUID = Field(default_factory=uuid4)
    asset_symbol: str
    time_range: str | tuple[str, str] | tuple[datetime, datetime]
    embedding: list[float]
    emb_type: str = Field(default="ts2vec")
    emb_version: str = Field(default="v1")
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
    config: dict[str, Any]
    metrics: dict[str, Any]
    artifacts: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DriftEventRecord(BaseModel):
    """Structured payload for entries in the drift events table."""

    metric: str
    trigger_type: str
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)


@dataclass
class FeatureRegistryEntry:
    """Structured representation for entries in the feature registry."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    version: str = ""
    path: str = ""
    description: str = ""
    status: str = "proposed"
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = str(self.id)
        return payload


@_retryable()
def insert_embeddings(records: Sequence[EmbeddingRecord | dict[str, Any]]) -> list[dict[str, Any]]:
    """Bulk upsert embeddings into the `signal_embeddings` table."""

    client = get_supabase_client()
    payload: list[dict[str, Any]] = []
    for record in records:
        model = record if isinstance(record, EmbeddingRecord) else EmbeddingRecord(**record)
        serialized = model.model_dump()
        serialized["id"] = str(serialized["id"])
        serialized["updated_at"] = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
        payload.append(serialized)
    response = (
        client.table("signal_embeddings")
        .upsert(payload, on_conflict="asset_symbol,time_range,emb_type,emb_version")
        .execute()
    )
    data = getattr(response, "data", None)
    if data is None:
        return list(payload)
    return cast(list[dict[str, Any]], data)


@_retryable()
def nearest(
    query_embedding: Sequence[float],
    *,
    k: int = 5,
    filter_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Query the closest vectors using the `match_signal_embeddings` RPC."""

    client = get_supabase_client()
    payload = {
        "query_embedding": list(query_embedding),
        "match_count": k,
        "filter": filter_params or {},
    }
    response = client.rpc("match_signal_embeddings", payload).execute()
    data = getattr(response, "data", None)
    if data is None:
        return []
    return cast(list[dict[str, Any]], data)


def fetch_nearest(
    query_embedding: Sequence[float],
    *,
    match_count: int = 5,
    filter_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Backward compatible wrapper for the `nearest` helper."""

    return cast(
        list[dict[str, Any]],
        nearest(query_embedding, k=match_count, filter_params=filter_params),
    )


@_retryable()
def insert_backtest_result(result: BacktestResult | dict[str, Any]) -> dict[str, Any]:
    """Insert a backtest result row into Supabase."""

    model = result if isinstance(result, BacktestResult) else BacktestResult(**result)
    payload = model.model_dump()
    payload["id"] = str(payload["id"])
    payload["created_at"] = payload["created_at"].isoformat()
    client = get_supabase_client()
    response = client.table("backtest_results").insert(payload).execute()
    data = getattr(response, "data", None)
    if not data:
        return payload
    if isinstance(data, list):
        return cast(dict[str, Any], data[0])
    return cast(dict[str, Any], data)


@_retryable()
def insert_drift_event(event: DriftEventRecord | dict[str, Any]) -> dict[str, Any]:
    """Insert a drift event entry and return the persisted payload."""

    model = event if isinstance(event, DriftEventRecord) else DriftEventRecord(**event)
    payload = model.model_dump()
    triggered_at = payload.get("triggered_at")
    if isinstance(triggered_at, datetime):
        payload["triggered_at"] = triggered_at.replace(tzinfo=timezone.utc).isoformat()
    client = get_supabase_client()
    response = client.table("drift_events").insert(payload).execute()
    data = getattr(response, "data", None)
    if not data:
        return payload
    if isinstance(data, list):
        return cast(dict[str, Any], data[0])
    return cast(dict[str, Any], data)


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


@_retryable()
def insert_feature(
    entry: FeatureRegistryEntry | dict[str, Any],
) -> list[dict[str, Any]] | dict[str, Any]:
    """Insert or update a feature registry entry in Supabase."""

    payload = entry.as_dict() if isinstance(entry, FeatureRegistryEntry) else entry
    client = get_supabase_client()
    response = client.table("feature_registry").upsert(payload, on_conflict="id").execute()
    data = getattr(response, "data", None)
    if data is None:
        return payload
    return cast(list[dict[str, Any]] | dict[str, Any], data)


def record_feature(
    entry: FeatureRegistryEntry | dict[str, Any],
) -> list[dict[str, Any]] | dict[str, Any]:
    """Deprecated alias for `insert_feature` retained for backward compatibility."""

    return cast(list[dict[str, Any]] | dict[str, Any], insert_feature(entry))


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


@_retryable()
def fetch_backtest_results(strategy_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Return recent backtest result rows for a given strategy."""

    client = get_supabase_client()
    response = (
        client.table("backtest_results")
        .select("id,strategy_id,config,metrics,artifacts,created_at")
        .eq("strategy_id", strategy_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    data = getattr(response, "data", None)
    if not data:
        return []
    if isinstance(data, list):
        return cast(list[dict[str, Any]], data)
    return [cast(dict[str, Any], data)]


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
    "DriftEventRecord",
    "EmbeddingRecord",
    "FeatureRegistryEntry",
    "MissingSupabaseConfiguration",
    "build_metadata",
    "fetch_backtest_results",
    "fetch_agent_state",
    "fetch_nearest",
    "get_supabase_client",
    "insert_feature",
    "insert_backtest_result",
    "insert_drift_event",
    "insert_embeddings",
    "nearest",
    "list_failed_features",
    "list_pending_embedding_jobs",
    "mark_embedding_job_complete",
    "persist_agent_state",
    "record_feature",
    "store_artifact_file",
    "store_artifact_json",
]
