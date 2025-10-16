"""Feature generation utilities backed by Supabase pgvector."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from importlib import import_module, util
from typing import Any

import numpy as np
from framework.supabase_client import EmbeddingRecord


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
    rows: list[dict[str, Any]] = []
    for vector, timestamp in zip(embeddings, timestamps, strict=False):
        record = EmbeddingRecord(
            asset_symbol=asset_symbol,
            time_range=_format_time_range(timestamp, window_seconds),
            embedding=vector.tolist(),
            regime_tag=regime_tag,
            label=base_meta.get("label", {}),
            meta={k: v for k, v in base_meta.items() if k != "label"},
        )
        rows.append(record.dict())
    return rows


def fallback_identity_embeddings(
    *, timestamps: Sequence[datetime], values: np.ndarray, asset_symbol: str
) -> list[dict[str, Any]]:
    """Fallback helper that emits identity embeddings when TS2Vec is unavailable."""

    rows: list[dict[str, Any]] = []
    for idx, timestamp in enumerate(timestamps):
        vector = np.pad(values[idx], (0, max(0, 128 - values.shape[1])), mode="constant")[:128]
        record = EmbeddingRecord(
            asset_symbol=asset_symbol,
            time_range=_format_time_range(timestamp, 60),
            embedding=vector.tolist(),
        )
        rows.append(record.dict())
    return rows


__all__ = [
    "fallback_identity_embeddings",
    "generate_ts2vec_features",
]
