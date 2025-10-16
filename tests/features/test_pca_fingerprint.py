"""Unit tests for the PCA fingerprint helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from features.pca_fingerprint import (
    DEFAULT_PCA_ARTIFACT_PATH,
    PCA_COMPONENTS,
    fit_and_persist_pca,
    fit_pca_reducer,
    load_pca_reducer,
    project_to_fingerprint_width,
)


def test_fit_and_persist_roundtrip(tmp_path: Path) -> None:
    matrix = np.random.RandomState(0).randn(256, 256)
    artifact = tmp_path / "pca.pkl"
    reducer = fit_and_persist_pca(matrix, artifact_path=artifact, random_state=42)

    loaded = load_pca_reducer(artifact)
    reduced = loaded.transform(matrix)

    assert reducer.components_.shape[0] == PCA_COMPONENTS
    assert reduced.shape == (256, PCA_COMPONENTS)


def test_project_to_fingerprint_width_pads(tmp_path: Path) -> None:
    matrix = np.ones((5, 12))
    artifact = tmp_path / "pca.pkl"
    projected = project_to_fingerprint_width(matrix, artifact_path=artifact, fit_if_missing=False)
    assert projected.shape == (5, PCA_COMPONENTS)
    assert np.allclose(projected[:, :12], 1.0)


def test_project_to_fingerprint_width_requires_artifact(tmp_path: Path) -> None:
    matrix = np.random.RandomState(1).randn(10, 256)
    artifact = tmp_path / "missing.pkl"
    with pytest.raises(FileNotFoundError):
        project_to_fingerprint_width(matrix, artifact_path=artifact, fit_if_missing=False)


def test_project_to_fingerprint_width_fits_when_allowed(tmp_path: Path) -> None:
    matrix = np.random.RandomState(2).randn(256, 192)
    artifact = tmp_path / "auto_fit.pkl"
    projected = project_to_fingerprint_width(
        matrix,
        artifact_path=artifact,
        fit_if_missing=True,
        random_state=7,
    )
    assert projected.shape == (256, PCA_COMPONENTS)
    assert artifact.exists()


def test_fit_pca_reducer_validates_width() -> None:
    matrix = np.ones((4, 64))
    with pytest.raises(ValueError):
        fit_pca_reducer(matrix)


def test_default_artifact_path_constant() -> None:
    assert DEFAULT_PCA_ARTIFACT_PATH.as_posix().endswith("artifacts/pca/minirocket_128.pkl")
