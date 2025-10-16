"""Unit tests for the embeddings→fingerprints flow utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import types
from typing import Any
import logging

import numpy as np
import pandas as pd
import pytest

from flows.embeddings_and_fingerprints import (
    EmbedderConfig,
    EmbedderPayload,
    align_dimensions,
    build_fingerprint_records,
    concatenate_feature_blocks,
    execute_embedder,
    fingerprint_vectorization,
    upsert_fingerprint_rows,
    prepare_numeric_payload,
)


class _IdentityEmbedder:
    """Minimal callable class used for tests."""

    def __call__(self, values: np.ndarray, **_: object) -> np.ndarray:
        return values * 2


def _callable_identity(values: np.ndarray, **_: object) -> np.ndarray:
    return values + 1


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=3, freq="h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "window": ["a", "b", "c"],
            "feature_a": [1.0, 2.0, 3.0],
            "feature_b": [4.0, 5.0, 6.0],
        }
    )


def test_prepare_numeric_payload_dataframe(sample_dataframe: pd.DataFrame) -> None:
    matrix, metadata = prepare_numeric_payload(
        sample_dataframe,
        feature_columns=["feature_a", "feature_b"],
        metadata_columns=["timestamp", "window"],
    )
    assert matrix.shape == (3, 2)
    assert metadata[0]["window"] == "a"
    assert isinstance(metadata[1]["timestamp"], pd.Timestamp)


def test_prepare_numeric_payload_sequence() -> None:
    rows = [
        {"feature_a": 1, "feature_b": 2, "window": "a"},
        {"feature_a": 3, "feature_b": 4, "window": "b"},
    ]
    matrix, metadata = prepare_numeric_payload(
        rows,
        feature_columns=["feature_a", "feature_b"],
        metadata_columns=["window"],
    )
    assert matrix.tolist() == [[1.0, 2.0], [3.0, 4.0]]
    assert metadata == [{"window": "a"}, {"window": "b"}]


def test_concatenate_feature_blocks_validates_rows() -> None:
    block_a = np.ones((2, 3))
    block_b = np.zeros((2, 2))
    combined = concatenate_feature_blocks([block_a, block_b])
    assert combined.shape == (2, 5)


def test_concatenate_feature_blocks_mismatched_rows() -> None:
    block_a = np.ones((2, 3))
    block_b = np.zeros((3, 2))
    with pytest.raises(ValueError):
        concatenate_feature_blocks([block_a, block_b])


def test_align_dimensions_pads_to_canonical_width() -> None:
    matrix = np.ones((3, 4))
    aligned = align_dimensions(matrix, target_dim=128, use_pca=False)
    assert aligned.shape == (3, 128)
    assert np.allclose(aligned[:, :4], 1.0)


def test_align_dimensions_rejects_non_canonical_target() -> None:
    matrix = np.ones((2, 2))
    with pytest.raises(ValueError):
        align_dimensions(matrix, target_dim=64, use_pca=False)


def test_align_dimensions_requires_pca_when_width_exceeds() -> None:
    matrix = np.random.RandomState(3).randn(5, 256)
    with pytest.raises(ValueError):
        align_dimensions(matrix, target_dim=128, use_pca=False)


def test_align_dimensions_projects_with_pca(tmp_path: Path) -> None:
    matrix = np.random.RandomState(4).randn(256, 192)
    artifact = tmp_path / "pca.pkl"
    aligned = align_dimensions(
        matrix,
        target_dim=128,
        use_pca=True,
        pca_artifact_path=artifact,
        fit_pca_if_missing=True,
    )
    assert aligned.shape == (256, 128)
    assert artifact.exists()


def test_execute_embedder_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = "tests.flows.test_embeddings_and_fingerprints"
    config = EmbedderConfig(name="callable", callable_path=f"{module_path}._callable_identity")
    payload = EmbedderPayload(values=np.ones((2, 2)))
    result = execute_embedder(config, payload)
    assert np.allclose(result, 2.0)


def test_execute_embedder_class(monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = "tests.flows.test_embeddings_and_fingerprints"
    config = EmbedderConfig(name="class", callable_path=f"{module_path}._IdentityEmbedder")
    payload = EmbedderPayload(values=np.ones((2, 2)))
    result = execute_embedder(config, payload)
    assert np.allclose(result, 2.0)


def test_build_fingerprint_records() -> None:
    vectors = np.ones((2, 3))
    metadata = [
        {
            "window_start": datetime(2024, 1, 1, 9),
            "window_end": datetime(2024, 1, 1, 10),
        },
        {
            "window_start": datetime(2024, 1, 2, 9),
            "window_end": datetime(2024, 1, 2, 10),
        },
    ]
    records = build_fingerprint_records(
        vectors=vectors,
        signal_name="demo",
        signal_version="v1",
        asset_symbol="XYZ",
        window_metadata=metadata,
        provenance={
            "embedders": ["test"],
            "feature_version": "fingerprint-demo",
            "source_url": ["memory"],
        },
        base_metadata={"source": "unit"},
    )
    assert len(records) == 2
    assert records[0]["meta"]["source"] == "unit"
    assert records[0]["window_start"] == "2024-01-01"
    assert "fingerprint_sha256" in records[0]["provenance"]


def test_upsert_fingerprint_rows_uses_conflict_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _DummyTable:
        def upsert(self, rows, on_conflict=None):  # type: ignore[no-untyped-def]
            captured["rows"] = list(rows)
            captured["on_conflict"] = on_conflict
            return self

        def execute(self):  # type: ignore[no-untyped-def]
            return types.SimpleNamespace(data=[{"id": "existing"}])

    class _DummyClient:
        def table(self, name: str) -> _DummyTable:
            captured["table"] = name
            return _DummyTable()

    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints.get_supabase_client",
        lambda: _DummyClient(),
    )

    rows = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "signal_name": "demo",
            "version": "v1",
            "asset_symbol": "ACME",
            "window_start": "2024-01-01",
            "window_end": "2024-01-02",
            "fingerprint": [0.1, 0.2, 0.3],
            "provenance": {"source_url": ["unit"], "feature_version": "demo"},
            "meta": {},
            "table": "signal_fingerprints",
        }
    ]

    result = upsert_fingerprint_rows(rows)

    assert result == [{"id": "existing"}]
    assert captured["table"] == "signal_fingerprints"
    assert captured["on_conflict"] == "asset_symbol,window_start,window_end,version"
    assert "id" not in captured["rows"][0]
    assert "table" not in captured["rows"][0]


def test_upsert_fingerprint_rows_requires_conflict_columns() -> None:
    rows = [
        {
            "signal_name": "demo",
            "asset_symbol": "ACME",
            "window_start": "2024-01-01",
            "fingerprint": [0.1, 0.2, 0.3],
            "provenance": {"source_url": ["unit"], "feature_version": "demo"},
            "meta": {},
        }
    ]

    with pytest.raises(ValueError, match="idempotent upserts"):
        upsert_fingerprint_rows(rows)


def test_fingerprint_vectorization_builds_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubFuture:
        def __init__(self, value: Any):
            self._value = value

        def result(self) -> Any:
            return self._value

    class _StubTask:
        def __init__(self, fn):
            self._fn = fn

        def submit(self, rows, table_name):
            return _StubFuture(self._fn(rows, table_name))

    captured: dict[str, Any] = {}

    def _capture(rows, table_name):
        captured["rows"] = rows
        captured["table"] = table_name
        return rows

    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints._persist",
        _StubTask(_capture),
    )
    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints.get_run_logger",
        lambda: logging.getLogger("test"),
    )

    df = pd.DataFrame(
        {
            "window_start": [pd.Timestamp("2024-12-23"), pd.Timestamp("2024-12-24")],
            "window_end": [pd.Timestamp("2024-12-30"), pd.Timestamp("2024-12-31")],
            "feature_a": [1.0, 2.0],
        }
    )

    records = fingerprint_vectorization.fn(
        signal_name="demo",
        signal_version="v9",
        asset_symbol="ACME",
        embedder_configs=[],
        numeric_features=df,
        feature_columns=["feature_a"],
        metadata_columns=["window_start", "window_end"],
        base_metadata={"feature_version": "fingerprint-demo", "source_url": ["memory"]},
        use_pca=False,
        target_dim=128,
    )

    assert captured["table"] == "signal_fingerprints"
    assert len(records) == 2
    assert records[0]["signal_name"] == "demo"
    assert records[0]["window_end"] == "2024-12-30"


def test_fingerprint_vectorization_default_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubFuture:
        def __init__(self, value: Any):
            self._value = value

        def result(self) -> Any:
            return self._value

    class _StubTask:
        def __init__(self, fn):
            self._fn = fn

        def submit(self, rows, table_name):
            return _StubFuture(self._fn(rows, table_name))

    captured: dict[str, Any] = {}

    def _capture(rows, table_name):
        captured["rows"] = rows
        captured["table"] = table_name
        return rows

    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints._persist",
        _StubTask(_capture),
    )
    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints.get_run_logger",
        lambda: logging.getLogger("test"),
    )

    df = pd.DataFrame(
        {
            "window_start": [pd.Timestamp("2024-01-01")],
            "window_end": [pd.Timestamp("2024-01-02")],
            "feature_a": [1.0],
        }
    )

    fingerprint_vectorization.fn(
        signal_name="demo",
        signal_version="v1",
        asset_symbol="ACME",
        embedder_configs=[],
        numeric_features=df,
        feature_columns=["feature_a"],
        metadata_columns=["window_start", "window_end"],
        base_metadata={"feature_version": "fingerprint-demo", "source_url": ["memory"]},
    )

    assert captured["table"] == "signal_fingerprints"
    assert len(captured["rows"]) == 1
    fingerprint_lengths = {len(row["fingerprint"]) for row in captured["rows"]}
    assert fingerprint_lengths == {128}


def test_fingerprint_vectorization_rejects_non_canonical_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints.get_run_logger",
        lambda: logging.getLogger("test"),
    )

    df = pd.DataFrame(
        {
            "window_start": [pd.Timestamp("2024-01-01")],
            "window_end": [pd.Timestamp("2024-01-02")],
            "feature_a": [1.0],
        }
    )

    with pytest.raises(ValueError):
        fingerprint_vectorization.fn(
            signal_name="demo",
            signal_version="v1",
            asset_symbol="ACME",
            embedder_configs=[],
            numeric_features=df,
            feature_columns=["feature_a"],
            metadata_columns=["window_start", "window_end"],
            base_metadata={"feature_version": "fingerprint-demo", "source_url": ["memory"]},
            target_dim=64,
            use_pca=False,
        )


def test_fingerprint_vectorization_raises_when_block_exceeds_without_pca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints.get_run_logger",
        lambda: logging.getLogger("test"),
    )

    df = pd.DataFrame(
        {
            "window_start": [pd.Timestamp("2024-01-01")],
            "window_end": [pd.Timestamp("2024-01-02")],
            **{f"feature_{i}": [float(i)] for i in range(256)},
        }
    )

    with pytest.raises(ValueError):
        fingerprint_vectorization.fn(
            signal_name="demo",
            signal_version="v1",
            asset_symbol="ACME",
            embedder_configs=[],
            numeric_features=df,
            feature_columns=[f"feature_{i}" for i in range(256)],
            metadata_columns=["window_start", "window_end"],
            base_metadata={"feature_version": "fingerprint-demo", "source_url": ["memory"]},
            target_dim=128,
            use_pca=False,
        )
