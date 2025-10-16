"""MiniRocket-based embeddings for multivariate time-series panels."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


ArrayLike = NDArray[np.float_]


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

    MiniRocketMultivariate, from_3d_numpy_to_nested = _import_sktime()

    transformer = MiniRocketMultivariate(
        num_kernels=num_features, random_state=random_state
    )
    nested = from_3d_numpy_to_nested(clean_panel)
    features = transformer.fit_transform(nested)
    feature_array = features.to_numpy(dtype=float)
    return [row.tolist() for row in feature_array]


__all__ = ["generate_minirocket_embeddings"]
def _import_sktime() -> tuple[object, object]:
    try:
        from sktime.transformations.panel.rocket import MiniRocketMultivariate
        from sktime.utils.data_processing import from_3d_numpy_to_nested
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise ModuleNotFoundError(
            "MiniRocket embeddings require the optional dependency 'sktime'. "
            "Install it with `pip install sktime`."
        ) from exc
    return MiniRocketMultivariate, from_3d_numpy_to_nested
