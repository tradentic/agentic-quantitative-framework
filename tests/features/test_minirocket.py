"""Unit tests for MiniRocket embedding utilities."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("sktime")

from features.minirocket_embeddings import generate_minirocket_embeddings


def test_embeddings_shape_and_type() -> None:
    panel = np.random.RandomState(0).randn(5, 3, 50)
    embeddings = generate_minirocket_embeddings(panel, num_features=64, random_state=123)

    assert len(embeddings) == 5
    assert all(len(vector) == 64 for vector in embeddings)
    assert all(isinstance(value, float) for vector in embeddings for value in vector)


def test_embeddings_deterministic_with_seed() -> None:
    panel = np.random.RandomState(42).rand(3, 2, 30)

    emb1 = generate_minirocket_embeddings(panel, num_features=32, random_state=1)
    emb2 = generate_minirocket_embeddings(panel, num_features=32, random_state=1)
    emb3 = generate_minirocket_embeddings(panel, num_features=32, random_state=2)

    assert np.allclose(emb1, emb2)
    assert not np.allclose(emb1, emb3)


def test_invalid_arguments() -> None:
    panel = np.ones((2, 10))

    with pytest.raises(ValueError):
        generate_minirocket_embeddings(panel, num_features=0)

    with pytest.raises(TypeError):
        generate_minirocket_embeddings(panel.astype(object))
