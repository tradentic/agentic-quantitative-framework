"""Unit tests for the embeddings→fingerprints flow utilities."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from flows.embeddings_and_fingerprints import (
    EmbedderConfig,
    EmbedderPayload,
    align_dimensions,
    apply_pca_projection,
    build_fingerprint_records,
    concatenate_feature_blocks,
    execute_embedder,
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


def test_apply_pca_projection_reduces_dimensionality() -> None:
    matrix = np.arange(20, dtype=float).reshape(5, 4)
    projected = apply_pca_projection(matrix, target_dim=2)
    assert projected.shape == (5, 2)


def test_align_dimensions_padding() -> None:
    matrix = np.ones((3, 4))
    aligned = align_dimensions(matrix, target_dim=6, use_pca=False)
    assert aligned.shape == (3, 6)
    assert np.allclose(aligned[:, :4], 1.0)


def test_align_dimensions_requires_pca() -> None:
    matrix = np.ones((3, 6))
    with pytest.raises(ValueError):
        align_dimensions(matrix, target_dim=4, use_pca=False)


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
    metadata = [{"timestamp": datetime(2024, 1, 1, 9)}, {"timestamp": datetime(2024, 1, 1, 10)}]
    records = build_fingerprint_records(
        vectors=vectors,
        asset_symbol="XYZ",
        window_metadata=metadata,
        provenance={"embedders": ["test"]},
        base_metadata={"source": "unit"},
    )
    assert len(records) == 2
    assert records[0]["meta"]["source"] == "unit"
    assert records[0]["as_of"].startswith("2024-01-01T09:00:00")
