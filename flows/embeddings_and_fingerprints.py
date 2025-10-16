"""Compose embeddings and numeric features into Supabase fingerprint vectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from importlib import import_module
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

import numpy as np
import pandas as pd
from prefect import flow, get_run_logger, task

from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client


@dataclass(frozen=True, slots=True)
class EmbedderConfig:
    """Declarative configuration for embedding callables."""

    name: str
    callable_path: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbedderPayload:
    """Shared payload passed to every embedder."""

    values: np.ndarray
    timestamps: Sequence[datetime] | None = None
    asset_symbol: str | None = None
    metadata: Mapping[str, Any] | None = None

    def as_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments without ``None`` entries."""

        kwargs: dict[str, Any] = {"values": self.values}
        if self.timestamps is not None:
            kwargs["timestamps"] = self.timestamps
        if self.asset_symbol is not None:
            kwargs["asset_symbol"] = self.asset_symbol
        if self.metadata:
            kwargs["metadata"] = dict(self.metadata)
        return kwargs


def _resolve_callable(path: str) -> Callable[..., Any]:
    """Resolve a dotted path into a callable, raising descriptive errors."""

    module_path, _, attr = path.rpartition(".")
    if not module_path:
        raise ValueError(f"Embedder callable path '{path}' is not a valid dotted path.")
    module = import_module(module_path)
    try:
        target = getattr(module, attr)
    except AttributeError as exc:  # pragma: no cover - import error path
        raise AttributeError(f"Module '{module_path}' has no attribute '{attr}'.") from exc
    if isinstance(target, type):
        return target  # Allow classes; instantiation handled downstream.
    if not callable(target):
        raise TypeError(f"Resolved object at '{path}' is not callable.")
    return target


def _coerce_matrix(result: Any) -> np.ndarray:
    """Convert embedder outputs into a 2D float matrix."""

    array = np.asarray(result, dtype=float)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2:
        raise ValueError("Embedder output must be coercible to a 2D matrix of floats.")
    return array


def execute_embedder(config: EmbedderConfig, payload: EmbedderPayload) -> np.ndarray:
    """Invoke an embedder and coerce the result into a matrix."""

    if not config.enabled:
        return np.empty((payload.values.shape[0], 0))

    try:
        target = _resolve_callable(config.callable_path)
    except ModuleNotFoundError:  # pragma: no cover - depends on optional deps
        return payload.values.copy()

    kwargs = {**config.params, **payload.as_kwargs()}

    if isinstance(target, type):
        instance = target(**config.params)
        if hasattr(instance, "fit_transform"):
            return _coerce_matrix(instance.fit_transform(payload.values))
        if callable(instance):
            return _coerce_matrix(instance(**payload.as_kwargs()))
        raise TypeError(
            f"Embedder '{config.name}' resolved to a class without a callable interface."
        )

    return _coerce_matrix(target(**kwargs))


def prepare_numeric_payload(
    numeric_features: pd.DataFrame | Sequence[Mapping[str, Any]] | None,
    *,
    feature_columns: Sequence[str] | None = None,
    metadata_columns: Sequence[str] | None = None,
) -> tuple[np.ndarray | None, list[dict[str, Any]]]:
    """Extract numeric arrays and metadata rows from heterogeneous inputs."""

    if numeric_features is None:
        return None, []

    if isinstance(numeric_features, pd.DataFrame):
        df = numeric_features.copy()
        meta_cols = list(metadata_columns or [])
        if feature_columns is None:
            feature_columns = [
                col
                for col in df.columns
                if col not in meta_cols and pd.api.types.is_numeric_dtype(df[col])
            ]
        matrix = df[feature_columns].astype(float).fillna(0.0).to_numpy()
        metadata = (
            df[meta_cols].to_dict("records") if meta_cols else [{} for _ in range(len(df))]
        )
        return matrix, metadata

    rows = list(numeric_features)
    if not rows:
        return None, []

    if feature_columns is None:
        raise ValueError("feature_columns must be provided for sequence inputs.")

    matrix_data = []
    metadata: list[dict[str, Any]] = []
    meta_cols = list(metadata_columns or [])
    for row in rows:
        row_map = dict(row)
        matrix_data.append([float(row_map.get(col, 0.0)) for col in feature_columns])
        metadata.append({col: row_map.get(col) for col in meta_cols})
    matrix = np.asarray(matrix_data, dtype=float)
    return matrix, metadata


def concatenate_feature_blocks(blocks: Sequence[np.ndarray]) -> np.ndarray:
    """Horizontally stack non-empty feature blocks after validating row counts."""

    filtered = [block for block in blocks if block.size]
    if not filtered:
        raise ValueError("At least one feature block must be provided.")

    row_counts = {block.shape[0] for block in filtered}
    if len(row_counts) != 1:
        raise ValueError("All feature blocks must have the same number of rows.")

    return np.hstack(filtered)


def apply_pca_projection(matrix: np.ndarray, target_dim: int) -> np.ndarray:
    """Project the matrix to ``target_dim`` dimensions using SVD-based PCA."""

    if target_dim <= 0:
        raise ValueError("target_dim must be a positive integer.")
    if matrix.shape[1] <= target_dim:
        return matrix

    centered = matrix - matrix.mean(axis=0, keepdims=True)
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[:target_dim]
    return centered @ components.T


def align_dimensions(
    matrix: np.ndarray,
    *,
    target_dim: int | None,
    use_pca: bool,
) -> np.ndarray:
    """Match the desired dimensionality via optional PCA or zero-padding."""

    if target_dim is None:
        return matrix
    if matrix.shape[1] == target_dim:
        return matrix
    if matrix.shape[1] < target_dim:
        padding = np.zeros((matrix.shape[0], target_dim - matrix.shape[1]))
        return np.hstack([matrix, padding])
    if use_pca:
        return apply_pca_projection(matrix, target_dim)
    raise ValueError(
        "Feature dimensionality exceeds target_dim and PCA is disabled."
    )


def build_fingerprint_records(
    *,
    vectors: np.ndarray,
    asset_symbol: str,
    window_metadata: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
    base_metadata: Mapping[str, Any] | None = None,
    timestamp_field: str = "timestamp",
    table_name: str = "signal_fingerprints",
) -> list[dict[str, Any]]:
    """Assemble payloads ready for Supabase upsert operations."""

    if window_metadata and len(window_metadata) != vectors.shape[0]:
        raise ValueError("window_metadata length must match the number of vectors.")

    records: list[dict[str, Any]] = []
    default_meta = dict(base_metadata or {})
    for idx, vector in enumerate(vectors):
        row_meta = dict(default_meta)
        if window_metadata:
            row_meta.update(window_metadata[idx])
        as_of = row_meta.get(timestamp_field) or row_meta.get("as_of")
        if isinstance(as_of, datetime):
            as_of = as_of.isoformat()
        record = {
            "id": str(uuid4()),
            "asset_symbol": asset_symbol,
            "as_of": as_of,
            "fingerprint": vector.astype(float).tolist(),
            "provenance": dict(provenance),
            "meta": row_meta,
            "table": table_name,
        }
        records.append(record)
    return records


def upsert_fingerprint_rows(
    rows: Sequence[dict[str, Any]],
    *,
    table_name: str = "signal_fingerprints",
) -> list[dict[str, Any]]:
    """Persist fingerprint vectors into Supabase, returning the inserted rows."""

    if not rows:
        return []
    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        return list(rows)

    payload = [
        {k: v for k, v in row.items() if k != "table"}
        for row in rows
    ]
    response = client.table(table_name).upsert(payload).execute()
    data = getattr(response, "data", None)
    if data is None:  # pragma: no cover - depends on client behaviour
        return list(payload)
    return list(data)


@task
def _run_embedder(config: EmbedderConfig, payload: EmbedderPayload) -> np.ndarray:
    return execute_embedder(config, payload)


@task
def _persist(rows: Sequence[dict[str, Any]], table_name: str) -> list[dict[str, Any]]:
    return upsert_fingerprint_rows(rows, table_name=table_name)


@flow(name="fingerprint-vectorization")
def fingerprint_vectorization(
    *,
    asset_symbol: str,
    embedder_configs: Sequence[EmbedderConfig],
    numeric_features: pd.DataFrame | Sequence[Mapping[str, Any]] | None,
    feature_columns: Sequence[str] | None = None,
    metadata_columns: Sequence[str] | None = None,
    timestamps: Sequence[datetime] | None = None,
    base_metadata: Mapping[str, Any] | None = None,
    target_dim: int | None = 256,
    use_pca: bool = True,
    table_name: str = "signal_fingerprints",
) -> list[dict[str, Any]]:
    """Prefect flow that builds and persists signal fingerprint vectors."""

    logger = get_run_logger()
    matrix, window_metadata = prepare_numeric_payload(
        numeric_features,
        feature_columns=feature_columns,
        metadata_columns=metadata_columns,
    )
    if matrix is None:
        raise ValueError("numeric_features must provide at least one row of data.")

    payload = EmbedderPayload(
        values=matrix,
        timestamps=timestamps,
        asset_symbol=asset_symbol,
        metadata=base_metadata,
    )

    embedder_blocks: list[np.ndarray] = []
    enabled = [config for config in embedder_configs if config.enabled]
    if not enabled:
        logger.warning("No embedder configs enabled; using numeric features only.")
    for config in enabled:
        block = _run_embedder.submit(config, payload)
        embedder_blocks.append(block.result())
        logger.info("Loaded embedder '%s' with %d dims", config.name, embedder_blocks[-1].shape[1])

    blocks = embedder_blocks + [matrix]
    feature_matrix = concatenate_feature_blocks(blocks)
    logger.info("Combined feature matrix shape: %s", feature_matrix.shape)

    aligned = align_dimensions(feature_matrix, target_dim=target_dim, use_pca=use_pca)
    logger.info("Aligned matrix shape: %s", aligned.shape)

    provenance = {
        "embedders": [config.name for config in enabled],
        "feature_columns": list(feature_columns or []),
        "metadata_columns": list(metadata_columns or []),
        "target_dim": target_dim,
        "pca": use_pca,
    }

    records = build_fingerprint_records(
        vectors=aligned,
        asset_symbol=asset_symbol,
        window_metadata=window_metadata,
        provenance=provenance,
        base_metadata=base_metadata,
        table_name=table_name,
    )
    logger.info("Prepared %d fingerprint records", len(records))

    persisted = _persist.submit(records, table_name).result()
    logger.info("Persisted %d fingerprint rows", len(persisted))
    return persisted


__all__ = [
    "EmbedderConfig",
    "EmbedderPayload",
    "apply_pca_projection",
    "build_fingerprint_records",
    "concatenate_feature_blocks",
    "fingerprint_vectorization",
    "prepare_numeric_payload",
    "upsert_fingerprint_rows",
]
