# MiniRocket Embeddings

## Motivation
MiniRocket offers state-of-the-art speed for convolutional feature extraction over time-series panels, enabling lightweight embeddings that remain expressive for downstream anomaly detection, clustering, or labeling workflows.

## Inputs / Outputs
* **Input:** Numeric panel windows supplied as a NumPy array with shape `(n_instances, n_channels, series_length)` or `(n_instances, series_length)`.
* **Output:** Python lists of floats, each representing a fixed-length MiniRocket feature vector suitable for serialization or insertion into vector stores.

## Configurations
* `num_features` — controls the number of kernels/features to generate (default `10_000`).
* `random_state` — optional seed to guarantee deterministic embeddings across runs.

## CLI Example
```bash
python - <<'PY'
import numpy as np
from features.minirocket_embeddings import generate_minirocket_embeddings

panel = np.random.RandomState(0).randn(4, 2, 60)
embeddings = generate_minirocket_embeddings(panel, num_features=256, random_state=7)
print(len(embeddings), len(embeddings[0]))
PY
```

## Failure Modes
* Missing `sktime` dependency raises a `ModuleNotFoundError` at call time with explicit installation instructions; the module itself imports without `sktime` installed so pipelines can still load.
* Invalid array shapes or non-numeric dtypes raise descriptive `TypeError`/`ValueError` exceptions.
* Requesting zero or negative `num_features` triggers a `ValueError` to prevent invalid MiniRocket configurations.

## Validation Checks
* Unit tests confirm embedding shape, dtype, and determinism for a fixed seed.
* All vectors are returned as pure Python lists, ensuring compatibility with JSON-based pipelines and pgvector ingestion.
