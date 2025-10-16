"""Feature generation utilities backed by Supabase pgvector."""

from __future__ import annotations

from datetime import datetime
from importlib import import_module, util
from typing import Any, Dict, Iterable, Sequence

import numpy as np
import pandas as pd

from agents.tools import batch_upsert_embeddings
from framework.supabase_client import build_metadata


def _load_ts2vec() -> Any:
    if util.find_spec("ts2vec") is None:
        raise ModuleNotFoundError("TS2Vec is required for embedding generation. Install it with `pip install ts2vec`.")
    module = import_module("ts2vec")
    return getattr(module, "TS2Vec")


def _prepare_embedding_records(
    embedding_matrix: np.ndarray,
    asset_id: str,
    window_timestamps: Sequence[pd.Timestamp],
    metadata: Dict[str, Any] | None = None,
) -> Iterable[Dict[str, Any]]:
    base_metadata = build_metadata(metadata)
    for vector, timestamp in zip(embedding_matrix, window_timestamps):
        yield {
            "asset_id": asset_id,
            "observed_at": timestamp.isoformat(),
            "embedding": vector.tolist(),
            "metadata": base_metadata,
        }


def generate_ts2vec_features(
    time_series: pd.DataFrame,
    asset_id: str,
    *,
    metadata: Dict[str, Any] | None = None,
    epochs: int = 20,
) -> np.ndarray:
    """Create TS2Vec embeddings and push them to Supabase pgvector storage."""

    if not isinstance(time_series, pd.DataFrame):
        raise TypeError("`time_series` must be a pandas DataFrame with datetime index.")
    if not isinstance(time_series.index, pd.DatetimeIndex):
        raise TypeError("`time_series` requires a DatetimeIndex to timestamp embeddings.")

    ts2vec_cls = _load_ts2vec()
    encoder = ts2vec_cls(input_dims=time_series.shape[1])
    embeddings = encoder.fit_transform(time_series.values, n_epochs=epochs)

    records = _prepare_embedding_records(
        embeddings,
        asset_id,
        time_series.index.to_pydatetime(),
        metadata={**(metadata or {}), "generated_at": datetime.utcnow().isoformat()},
    )
    batch_upsert_embeddings(records)
    return embeddings
