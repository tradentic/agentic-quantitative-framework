"""MiniRocket optional dependency tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.minirocket_embeddings import (
    DependencyUnavailable,
    SKTIME_AVAILABLE,
    generate_minirocket_embeddings,
)


@pytest.mark.skipif(not SKTIME_AVAILABLE, reason="sktime not installed")
def test_generate_minirocket_embeddings_smoke() -> None:
    """MiniRocket produces deterministic feature dimensions when available."""

    rng = np.random.default_rng(0)
    panel = rng.standard_normal((2, 3, 20)).astype(np.float32)
    embeddings = generate_minirocket_embeddings(panel, num_features=32, random_state=0)

    assert len(embeddings) == 2
    assert all(len(vec) == 32 for vec in embeddings)


@pytest.mark.skipif(SKTIME_AVAILABLE, reason="sktime installed")
def test_dependency_unavailable_when_sktime_missing() -> None:
    """Without sktime, MiniRocket raises a controlled dependency error."""

    panel = np.ones((1, 10), dtype=np.float32)

    with pytest.raises(DependencyUnavailable):
        generate_minirocket_embeddings(panel)
