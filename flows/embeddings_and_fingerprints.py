"""Compose embeddings and numeric features into Supabase fingerprint vectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

import numpy as np
import pandas as pd
from prefect import flow, get_run_logger, task

from features.pca_fingerprint import (
    DEFAULT_PCA_ARTIFACT_PATH,
    PCA_COMPONENTS,
    project_to_fingerprint_width,
)
from framework.provenance import hash_bytes
from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client
from utils.guards import SkipStep, ensure_not_empty


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
        df = ensure_not_empty(numeric_features, "numeric feature frame").copy()
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
        raise SkipStep("numeric feature records are empty")

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


def align_dimensions(
    matrix: np.ndarray,
    *,
    target_dim: int | None,
    use_pca: bool,
    pca_artifact_path: str | Path | None = None,
    fit_pca_if_missing: bool = True,
) -> np.ndarray:
    """Match the desired dimensionality via optional PCA or zero-padding."""

    target = target_dim or PCA_COMPONENTS
    if target != PCA_COMPONENTS:
        raise ValueError(
            f"Fingerprint vectors must remain {PCA_COMPONENTS} dimensions; "
            f"received target_dim={target}."
        )

    if matrix.shape[1] == target:
        return matrix
    if matrix.shape[1] < target:
        padding = np.zeros((matrix.shape[0], target - matrix.shape[1]))
        return np.hstack([matrix, padding])
    if not use_pca:
        raise ValueError(
            "Feature dimensionality %d exceeds the canonical width %d while PCA is disabled."
            % (matrix.shape[1], target)
        )

    artifact = Path(pca_artifact_path) if pca_artifact_path is not None else DEFAULT_PCA_ARTIFACT_PATH
    return project_to_fingerprint_width(
        matrix,
        artifact_path=artifact,
        fit_if_missing=fit_pca_if_missing,
    )


def build_fingerprint_records(
    *,
    vectors: np.ndarray,
    signal_name: str,
    signal_version: str,
    asset_symbol: str,
    window_metadata: Sequence[Mapping[str, Any]] | None,
    provenance: Mapping[str, Any],
    base_metadata: Mapping[str, Any] | None = None,
    window_start_field: str = "window_start",
    window_end_field: str = "window_end",
    fallback_timestamp_field: str = "timestamp",
    table_name: str = "signal_fingerprints",
) -> list[dict[str, Any]]:
    """Assemble payloads ready for Supabase upsert operations."""

    if window_metadata and len(window_metadata) != vectors.shape[0]:
        raise ValueError("window_metadata length must match the number of vectors.")

    if "feature_version" not in provenance or "source_url" not in provenance:
        raise ValueError("provenance must include 'feature_version' and 'source_url'.")

    records: list[dict[str, Any]] = []
    default_meta = dict(base_metadata or {})

    def _coerce_date(value: Any) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str) and value:
            return value
        raise ValueError("Fingerprint records require window_start/window_end metadata.")

    for idx, vector in enumerate(vectors):
        row_meta = dict(default_meta)
        if window_metadata:
            row_meta.update(window_metadata[idx])
        window_start_raw = (
            row_meta.get(window_start_field)
            or row_meta.get(fallback_timestamp_field)
            or row_meta.get("as_of")
        )
        window_end_raw = (
            row_meta.get(window_end_field)
            or row_meta.get(fallback_timestamp_field)
            or row_meta.get("as_of")
        )
        window_start = _coerce_date(window_start_raw)
        window_end = _coerce_date(window_end_raw)

        vector_list = vector.astype(float).tolist()
        vector_hash = hash_bytes(np.asarray(vector_list, dtype=float).tobytes())
        record_provenance = dict(provenance)
        record_provenance["fingerprint_sha256"] = vector_hash

        record = {
            "id": str(uuid4()),
            "signal_name": signal_name,
            "version": signal_version,
            "asset_symbol": asset_symbol,
            "window_start": window_start,
            "window_end": window_end,
            "fingerprint": vector_list,
            "provenance": record_provenance,
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

    required_conflict_keys = {"asset_symbol", "window_start", "window_end", "version"}
    for row in rows:
        missing_keys = required_conflict_keys.difference(row)
        if missing_keys:
            raise ValueError(
                "Fingerprint rows must include %s for idempotent upserts; missing %s"
                % (", ".join(sorted(required_conflict_keys)), ", ".join(sorted(missing_keys)))
            )

    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        return list(rows)

    payload: list[dict[str, Any]] = []
    for row in rows:
        sanitized = {
            key: value
            for key, value in row.items()
            if key not in {"table", "id"}
        }
        payload.append(sanitized)
    response = (
        client.table(table_name)
        .upsert(payload, on_conflict="asset_symbol,window_start,window_end,version")
        .execute()
    )
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
    signal_name: str,
    signal_version: str = "v1",
    asset_symbol: str,
    embedder_configs: Sequence[EmbedderConfig],
    numeric_features: pd.DataFrame | Sequence[Mapping[str, Any]] | None,
    feature_columns: Sequence[str] | None = None,
    metadata_columns: Sequence[str] | None = None,
    timestamps: Sequence[datetime] | None = None,
    base_metadata: Mapping[str, Any] | None = None,
    target_dim: int | None = 128,
    use_pca: bool = True,
    pca_artifact_path: str | Path | None = None,
    fit_pca_if_missing: bool = True,
    table_name: str = "signal_fingerprints",
    provenance_overrides: Mapping[str, Any] | None = None,
    window_start_field: str = "window_start",
    window_end_field: str = "window_end",
    fallback_timestamp_field: str = "timestamp",
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

    block_info: list[tuple[str, np.ndarray]] = []
    enabled = [config for config in embedder_configs if config.enabled]
    if not enabled:
        logger.warning("No embedder configs enabled; using numeric features only.")
    for config in enabled:
        block = _run_embedder.submit(config, payload)
        value = block.result()
        block_info.append((config.name, value))
        logger.info("Loaded embedder '%s' with %d dims", config.name, value.shape[1])

    block_info.append(("numeric_features", matrix))

    canonical_width = target_dim or PCA_COMPONENTS
    block_shapes = {name: block.shape[1] for name, block in block_info}
    if not use_pca:
        exceeding = {name: width for name, width in block_shapes.items() if width > canonical_width}
        if exceeding:
            raise ValueError(
                "Feature block dimensionality exceeds the canonical width %d: %s"
                % (canonical_width, exceeding)
            )

    blocks = [block for _, block in block_info]
    feature_matrix = concatenate_feature_blocks(blocks)
    logger.info("Combined feature matrix shape: %s", feature_matrix.shape)

    aligned = align_dimensions(
        feature_matrix,
        target_dim=target_dim,
        use_pca=use_pca,
        pca_artifact_path=pca_artifact_path,
        fit_pca_if_missing=fit_pca_if_missing,
    )
    logger.info("Aligned matrix shape: %s", aligned.shape)

    if aligned.shape[1] != PCA_COMPONENTS:
        raise ValueError(
            "Fingerprint projection must output %d dimensions; received %d (block widths: %s)."
            % (PCA_COMPONENTS, aligned.shape[1], block_shapes)
        )

    provenance = {
        "embedders": [config.name for config in enabled],
        "feature_columns": list(feature_columns or []),
        "metadata_columns": list(metadata_columns or []),
        "target_dim": target_dim,
        "pca": use_pca,
    }
    if base_metadata:
        if "feature_version" in base_metadata:
            provenance.setdefault("feature_version", base_metadata["feature_version"])
        if "source_url" in base_metadata:
            provenance.setdefault("source_url", base_metadata["source_url"])
    if provenance_overrides:
        provenance.update(provenance_overrides)
    if "feature_version" not in provenance or "source_url" not in provenance:
        raise ValueError("provenance must include 'feature_version' and 'source_url'.")

    records = build_fingerprint_records(
        vectors=aligned,
        signal_name=signal_name,
        signal_version=signal_version,
        asset_symbol=asset_symbol,
        window_metadata=window_metadata,
        provenance=provenance,
        base_metadata=base_metadata,
        window_start_field=window_start_field,
        window_end_field=window_end_field,
        fallback_timestamp_field=fallback_timestamp_field,
        table_name=table_name,
    )
    logger.info("Prepared %d fingerprint records", len(records))

    invalid_lengths = [
        (idx, len(row.get("fingerprint", [])))
        for idx, row in enumerate(records)
        if len(row.get("fingerprint", [])) != PCA_COMPONENTS
    ]
    if invalid_lengths:
        raise ValueError(
            "Fingerprint rows must contain %d values; found mismatches: %s"
            % (PCA_COMPONENTS, invalid_lengths)
        )

    persisted = _persist.submit(records, table_name).result()
    logger.info("Persisted %d fingerprint rows", len(persisted))
    return persisted


__all__ = [
    "EmbedderConfig",
    "EmbedderPayload",
    "build_fingerprint_records",
    "concatenate_feature_blocks",
    "fingerprint_vectorization",
    "prepare_numeric_payload",
    "upsert_fingerprint_rows",
]
