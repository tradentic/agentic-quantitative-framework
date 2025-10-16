"""MiniRocket-based embeddings for multivariate time-series panels."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray


if TYPE_CHECKING:  # pragma: no cover - typing helper for optional dependency
    from sktime.transformations.panel.rocket import MiniRocketMultivariate
    from sktime.utils.data_processing import from_3d_numpy_to_nested as _to_nested


logger = logging.getLogger(__name__)


ArrayLike = NDArray[np.float64]


class DependencyUnavailable(RuntimeError):
    """Raised when an optional dependency is not available at runtime."""


SKTIME_AVAILABLE: bool
IMPORT_ERR: Exception | None

try:  # pragma: no cover - exercised in integration tests when dependency present
    from sktime.transformations.panel.rocket import (
        MiniRocketMultivariate as MiniRocket,
    )
    from sktime.utils.data_processing import from_3d_numpy_to_nested as _to_nested
except Exception as exc:  # pragma: no cover - executed when sktime is missing
    SKTIME_AVAILABLE = False
    IMPORT_ERR = exc
    MiniRocket = None  # type: ignore[assignment]
    _to_nested = None  # type: ignore[assignment]
else:  # pragma: no cover - exercised when dependency is present
    SKTIME_AVAILABLE = True
    IMPORT_ERR = None


def _ensure_3d_panel(panel: np.ndarray) -> ArrayLike:
    """Validate and reshape a numeric array to the 3D panel format."""

    if not isinstance(panel, np.ndarray):
        raise TypeError("`panel` must be a numpy ndarray.")
    if panel.ndim not in (2, 3):
        raise ValueError(
            "`panel` must be a 2D or 3D array with shape (instances, [channels,] timesteps)."
        )
    if panel.dtype.kind not in {"f", "i", "u"}:
        raise TypeError("`panel` must contain numeric values.")

    if panel.ndim == 2:
        panel = panel[:, np.newaxis, :]
    if panel.shape[2] < 1:
        raise ValueError("`panel` must have at least one timestep.")

    return panel.astype(np.float32, copy=False)


def generate_minirocket_embeddings(
    panel: np.ndarray,
    *,
    num_features: int = 10_000,
    random_state: int | None = 0,
) -> list[list[float]]:
    """Compute MiniRocket embeddings for a numeric panel of time-series windows.

    Parameters
    ----------
    panel:
        Array of shape ``(n_instances, n_channels, series_length)`` or
        ``(n_instances, series_length)`` containing numeric values.
    num_features:
        Number of convolutional kernels/features to generate. Defaults to 10_000,
        which matches the MiniRocket paper recommendation. Must be positive.
    random_state:
        Optional seed controlling kernel selection. A fixed seed guarantees
        deterministic outputs across runs.

    Returns
    -------
    list[list[float]]
        Embedded vectors for each instance as Python lists to ensure downstream
        JSON serialization friendliness.

    Raises
    ------
    TypeError
        If ``panel`` is not a numpy array or contains non-numeric values.
    ValueError
        If ``panel`` has an invalid shape or ``num_features`` is not positive.
    """

    if num_features <= 0:
        raise ValueError("`num_features` must be a positive integer.")

    clean_panel = _ensure_3d_panel(panel)

    if not SKTIME_AVAILABLE or MiniRocket is None or _to_nested is None:
        logger.warning(
            "MiniRocket embeddings requested but optional dependency 'sktime' is unavailable: %s",
            IMPORT_ERR,
        )
        raise DependencyUnavailable("sktime/MiniRocket not installed") from IMPORT_ERR

    transformer = MiniRocket(num_kernels=num_features, random_state=random_state)
    nested = _to_nested(clean_panel)
    features = transformer.fit_transform(nested)
    feature_array = features.to_numpy(dtype=float)
    return [row.tolist() for row in feature_array]


__all__ = [
    "DependencyUnavailable",
    "SKTIME_AVAILABLE",
    "generate_minirocket_embeddings",
]
