"""Smoke tests for the MiniRocket embedding extractor."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:  # pragma: no cover - defensive path setup
    sys.path.insert(0, str(PROJECT_ROOT))

from features.minirocket_embeddings import (  # noqa: E402
    DependencyUnavailable,
    SKTIME_AVAILABLE,
    generate_minirocket_embeddings,
)


def test_minirocket_module_importable() -> None:
    """The module should import without raising even if sktime is absent."""

    # Import performed at module top-level; reaching this test indicates success.
    assert isinstance(SKTIME_AVAILABLE, bool)


@pytest.mark.skipif(not SKTIME_AVAILABLE, reason="sktime dependency not installed")
def test_generate_embeddings_when_dependency_available() -> None:
    """MiniRocket should emit deterministic feature vectors when available."""

    panel = np.ones((2, 3, 8), dtype=np.float32)
    features = generate_minirocket_embeddings(panel, num_features=32, random_state=0)

    assert len(features) == 2
    assert all(len(row) == 32 for row in features)


@pytest.mark.skipif(SKTIME_AVAILABLE, reason="dependency present; cannot exercise fallback")
def test_generate_embeddings_missing_dependency() -> None:
    """When sktime is missing, a controlled error is raised."""

    panel = np.ones((1, 10), dtype=np.float32)

    with pytest.raises(DependencyUnavailable):
        generate_minirocket_embeddings(panel, num_features=4, random_state=0)
