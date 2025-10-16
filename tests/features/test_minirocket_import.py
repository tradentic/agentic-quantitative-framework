"""Smoke tests for MiniRocket embedding utilities."""

from __future__ import annotations

import importlib

import numpy as np
import pytest

from features.minirocket_embeddings import (
    SKTIME_AVAILABLE,
    DependencyUnavailable,
    generate_minirocket_embeddings,
)


def test_module_import_smoke() -> None:
    """Ensure the MiniRocket embeddings module can be imported."""

    module = importlib.import_module("features.minirocket_embeddings")
    assert hasattr(module, "generate_minirocket_embeddings")


@pytest.mark.skipif(not SKTIME_AVAILABLE, reason="sktime is not available in the test environment")
def test_generate_minirocket_embeddings_smoke() -> None:
    """Run a tiny end-to-end MiniRocket embedding generation when sktime exists."""

    rng = np.random.default_rng(0)
    panel = rng.normal(size=(2, 3, 16)).astype(np.float32)

    embeddings = generate_minirocket_embeddings(panel, num_features=32, random_state=0)

    assert isinstance(embeddings, list)
    assert len(embeddings) == 2
    assert all(len(vec) == 32 for vec in embeddings)
    assert all(isinstance(value, (float, np.floating)) for vec in embeddings for value in vec)


@pytest.mark.skipif(SKTIME_AVAILABLE, reason="Only applicable when sktime is missing")
def test_dependency_unavailable_error() -> None:
    """When sktime is absent the embedding generator raises a clear error."""

    rng = np.random.default_rng(0)
    panel = rng.normal(size=(1, 10)).astype(np.float32)

    with pytest.raises(DependencyUnavailable):
        generate_minirocket_embeddings(panel)
