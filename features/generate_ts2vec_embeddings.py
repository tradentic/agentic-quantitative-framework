"""Feature generation utilities backed by Supabase pgvector."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from importlib import import_module, util
from typing import Any

import numpy as np
from framework.supabase_client import EmbeddingRecord

EMBEDDING_DIM = 128


def _clamp_embedding(vector: Sequence[float] | np.ndarray, *, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """Pad or truncate an embedding vector to match the pgvector dimension."""

    array = np.asarray(vector, dtype=float)
    if array.ndim == 0:
        array = array.reshape(1)
    elif array.ndim > 1:
        array = array.reshape(-1)

    length = array.shape[0]
    if length >= dim:
        return array[:dim]

    padded = np.zeros(dim, dtype=float)
    if length:
        padded[:length] = array
    return padded


def _load_ts2vec() -> Any:
    if util.find_spec("ts2vec") is None:
        raise ModuleNotFoundError(
            "TS2Vec is required for embedding generation. Install it with `pip install ts2vec`."
        )
    module = import_module("ts2vec")
    return module.TS2Vec


def _validate_inputs(
    timestamps: Sequence[datetime],
    values: np.ndarray,
) -> None:
    if not isinstance(values, np.ndarray):
        raise TypeError("`values` must be a numpy ndarray.")
    if values.ndim != 2:
        raise ValueError("`values` must be a 2D array of shape (windows, features).")
    if len(timestamps) != values.shape[0]:
        raise ValueError("Timestamp count must match the number of windows in `values`.")


def _format_time_range(timestamp: datetime, window_seconds: int) -> tuple[datetime, datetime]:
    delta = timedelta(seconds=window_seconds or 60)
    return timestamp, timestamp + delta


def generate_ts2vec_features(
    *,
    timestamps: Sequence[datetime],
    values: np.ndarray,
    asset_symbol: str,
    metadata: dict[str, Any] | None = None,
    regime_tag: str | None = None,
    window_seconds: int = 60,
) -> list[dict[str, Any]]:
    """Create TS2Vec embeddings and return structured rows for pgvector storage."""

    _validate_inputs(timestamps, values)

    try:
        ts2vec_cls = _load_ts2vec()
    except ModuleNotFoundError:
        return fallback_identity_embeddings(
            timestamps=timestamps,
            values=values,
            asset_symbol=asset_symbol,
        )

    encoder = ts2vec_cls(input_dims=values.shape[1])
    embeddings = encoder.fit_transform(values)

    base_meta = {**(metadata or {}), "generated_at": datetime.utcnow().isoformat()}
    base_meta["embedding_dim"] = EMBEDDING_DIM
    excluded_meta_keys = {"label", "emb_version", "emb_type"}
    rows: list[dict[str, Any]] = []
    for vector, timestamp in zip(embeddings, timestamps, strict=False):
        normalized_vector = _clamp_embedding(vector)
        record = EmbeddingRecord(
            asset_symbol=asset_symbol,
            time_range=_format_time_range(timestamp, window_seconds),
            embedding=normalized_vector.tolist(),
            emb_type="ts2vec",
            emb_version=metadata.get("emb_version", "v1") if metadata else "v1",
            regime_tag=regime_tag,
            label=base_meta.get("label", {}),
            meta={k: v for k, v in base_meta.items() if k not in excluded_meta_keys},
        )
        rows.append(record.dict())
    return rows


def fallback_identity_embeddings(
    *, timestamps: Sequence[datetime], values: np.ndarray, asset_symbol: str
) -> list[dict[str, Any]]:
    """Fallback helper that emits identity embeddings when TS2Vec is unavailable."""

    rows: list[dict[str, Any]] = []
    for idx, timestamp in enumerate(timestamps):
        vector = _clamp_embedding(values[idx])
        record = EmbeddingRecord(
            asset_symbol=asset_symbol,
            time_range=_format_time_range(timestamp, 60),
            embedding=vector.tolist(),
            emb_type="ts2vec",
            emb_version="v1",
            meta={"embedding_dim": EMBEDDING_DIM},
        )
        rows.append(record.dict())
    return rows


__all__ = [
    "fallback_identity_embeddings",
    "generate_ts2vec_features",
]
