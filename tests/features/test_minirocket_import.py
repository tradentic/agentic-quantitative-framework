"""Smoke tests for the MiniRocket embedding module import path."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


module = importlib.import_module("features.minirocket_embeddings")


def test_module_import_smoke() -> None:
    assert hasattr(module, "generate_minirocket_embeddings")
    assert hasattr(module, "SKTIME_AVAILABLE")


@pytest.mark.skipif(
    not getattr(module, "SKTIME_AVAILABLE", False),
    reason="sktime optional dependency is not installed",
)
def test_generate_embeddings_runs_smoke() -> None:
    panel = np.random.RandomState(1).randn(2, 5, 10)
    embeddings = module.generate_minirocket_embeddings(panel, num_features=4, random_state=0)

    assert len(embeddings) == 2
    assert all(len(vec) == 4 for vec in embeddings)
