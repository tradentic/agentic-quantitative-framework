"""Feature generation modules for embeddings and signals."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any

from .matrix_profile import MatrixProfileFeatures, compute_matrix_profile_metrics

__all__ = [
    "generate_ts2vec_embeddings",
    "deeplob_embeddings",
    "compute_matrix_profile_metrics",
    "MatrixProfileFeatures",
    "microstructure",
]


_OPTIONAL_MODULES = {
    "deeplob_embeddings": "features.deeplob_embeddings",
    "generate_ts2vec_embeddings": "features.generate_ts2vec_embeddings",
    "microstructure": "features.microstructure",
}


def __getattr__(name: str) -> Any:
    """Lazily import optional feature modules on first access."""

    if name in _OPTIONAL_MODULES:
        module = import_module(_OPTIONAL_MODULES[name])
        _cache_module(name, module)
        return module
    raise AttributeError(f"module 'features' has no attribute {name!r}")


def _cache_module(name: str, module: ModuleType) -> None:
    globals()[name] = module
