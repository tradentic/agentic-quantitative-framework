"""PCA helpers for maintaining canonical 128-d fingerprint vectors."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from joblib import dump, load
from sklearn.decomposition import PCA

PCA_COMPONENTS = 128
DEFAULT_PCA_ARTIFACT_PATH = Path("artifacts/pca/minirocket_128.pkl")


def _coerce_matrix(matrix: Iterable[Iterable[float]]) -> np.ndarray:
    array = np.asarray(matrix, dtype=float)
    if array.ndim != 2:
        raise ValueError("Input matrix must be 2-dimensional.")
    return array


def fit_pca_reducer(
    matrix: Iterable[Iterable[float]],
    *,
    n_components: int = PCA_COMPONENTS,
    random_state: int | None = 0,
) -> PCA:
    """Fit a PCA reducer that outputs the canonical fingerprint width."""

    array = _coerce_matrix(matrix)
    if array.shape[1] < n_components:
        raise ValueError(
            "Cannot fit PCA: input width %d is smaller than required components %d."
            % (array.shape[1], n_components)
        )
    reducer = PCA(n_components=n_components, svd_solver="auto", random_state=random_state)
    reducer.fit(array)
    if reducer.components_.shape[0] != n_components:
        raise ValueError(
            "Fitted PCA does not expose %d components (found %d)."
            % (n_components, reducer.components_.shape[0])
        )
    return reducer


def persist_pca_reducer(reducer: PCA, artifact_path: str | Path = DEFAULT_PCA_ARTIFACT_PATH) -> Path:
    """Persist a PCA reducer to disk using joblib, returning the saved path."""

    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dump(reducer, path)
    return path


def fit_and_persist_pca(
    matrix: Iterable[Iterable[float]],
    *,
    artifact_path: str | Path = DEFAULT_PCA_ARTIFACT_PATH,
    random_state: int | None = 0,
) -> PCA:
    """Fit a PCA reducer from the matrix and persist it to the canonical artifact path."""

    reducer = fit_pca_reducer(matrix, n_components=PCA_COMPONENTS, random_state=random_state)
    persist_pca_reducer(reducer, artifact_path=artifact_path)
    return reducer


def load_pca_reducer(artifact_path: str | Path = DEFAULT_PCA_ARTIFACT_PATH) -> PCA:
    """Load a persisted PCA reducer, validating that it emits 128 dimensions."""

    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(
            f"PCA artifact not found at '{path}'. Fit and persist it before loading."
        )
    reducer = load(path)
    components = getattr(reducer, "components_", None)
    if components is None:
        raise TypeError("Loaded object does not expose PCA components.")
    if components.shape[0] != PCA_COMPONENTS:
        raise ValueError(
            "Loaded PCA artifact provides %d components; expected %d."
            % (components.shape[0], PCA_COMPONENTS)
        )
    return reducer


def project_to_fingerprint_width(
    matrix: Iterable[Iterable[float]],
    *,
    artifact_path: str | Path = DEFAULT_PCA_ARTIFACT_PATH,
    fit_if_missing: bool = False,
    random_state: int | None = 0,
) -> np.ndarray:
    """Project a matrix to the canonical fingerprint width using the persisted PCA."""

    array = _coerce_matrix(matrix)
    if array.shape[1] == PCA_COMPONENTS:
        return array
    if array.shape[1] < PCA_COMPONENTS:
        padding = np.zeros((array.shape[0], PCA_COMPONENTS - array.shape[1]), dtype=float)
        return np.hstack([array, padding])

    path = Path(artifact_path)
    try:
        reducer = load_pca_reducer(path)
    except FileNotFoundError:
        if not fit_if_missing:
            raise
        reducer = fit_and_persist_pca(
            array,
            artifact_path=path,
            random_state=random_state,
        )
    transformed = reducer.transform(array)
    if transformed.shape[1] != PCA_COMPONENTS:
        raise ValueError(
            "Projected matrix has %d dimensions; expected %d."
            % (transformed.shape[1], PCA_COMPONENTS)
        )
    return transformed


__all__ = [
    "DEFAULT_PCA_ARTIFACT_PATH",
    "PCA_COMPONENTS",
    "fit_and_persist_pca",
    "fit_pca_reducer",
    "load_pca_reducer",
    "persist_pca_reducer",
    "project_to_fingerprint_width",
]
