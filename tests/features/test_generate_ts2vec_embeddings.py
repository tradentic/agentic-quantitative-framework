"""Unit tests for TS2Vec embedding generation helpers."""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _reload_module():
    return importlib.reload(importlib.import_module("features.generate_ts2vec_embeddings"))


def test_generate_ts2vec_features_clamps_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_module()

    class FakeTS2Vec:
        def __init__(self, input_dims: int) -> None:  # noqa: D401 - simple initializer
            self.input_dims = input_dims

        def fit_transform(self, values: np.ndarray) -> list[np.ndarray]:
            return [
                np.arange(64, dtype=float),
                np.arange(100, 300, dtype=float),
                np.arange(300, 428, dtype=float),
            ]

    monkeypatch.setattr(module, "_load_ts2vec", lambda: FakeTS2Vec)

    timestamps = [datetime(2024, 1, 1) + timedelta(minutes=i) for i in range(3)]
    values = np.ones((3, 4), dtype=float)
    metadata = {"label": {"class": "test"}, "source": "unit-test"}

    rows = module.generate_ts2vec_features(
        timestamps=timestamps,
        values=values,
        asset_symbol="TEST",
        metadata=metadata,
        regime_tag="mock",
        window_seconds=120,
    )

    assert len(rows) == 3
    assert all(len(row["embedding"]) == module.EMBEDDING_DIM for row in rows)

    padded_expected = np.pad(np.arange(64, dtype=float), (0, module.EMBEDDING_DIM - 64))
    truncated_expected = np.arange(100, 228, dtype=float)
    preserved_expected = np.arange(300, 428, dtype=float)

    np.testing.assert_array_equal(rows[0]["embedding"], padded_expected)
    np.testing.assert_array_equal(rows[1]["embedding"], truncated_expected)
    np.testing.assert_array_equal(rows[2]["embedding"], preserved_expected)

    meta = rows[0]["meta"]
    assert meta["embedding_dim"] == module.EMBEDDING_DIM
    assert meta["source"] == "unit-test"
    assert "generated_at" in meta

    label = rows[0]["label"]
    assert label == {"class": "test"}
