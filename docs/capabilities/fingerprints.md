# Fingerprint Vectorization Capability

## Motivation
- Compose heterogeneous embeddings and numeric signals into a single pgvector row for similarity search.
- Persist provenance-rich fingerprints that connect embeddings, market microstructure, and labeling context.
- Enable drift monitoring and downstream k-NN retrievals without duplicating feature engineering pipelines.

## Inputs
- Prefect flow parameters (`asset_symbol`, embedder configs, numeric feature frame or records).
- Optional timestamps aligned to embedding windows for metadata enrichment.
- Supabase configuration via `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` environment variables.

## Outputs
- Upserted rows in `signal_fingerprints` with `fingerprint` vectors, provenance, and metadata per window.
- Flow return value containing the Supabase response (or offline payload when credentials are absent).
- Prefect logs summarizing dimensionality alignment and persistence counts.

## Configuration & Usage Notes
- Declare embedders with `EmbedderConfig` (`name`, `callable_path`, `params`, `enabled`). Missing modules fall back to identity transforms.
- Provide numeric features as a pandas `DataFrame` or sequence of mappings; specify `feature_columns` and optional `metadata_columns`.
- Use `target_dim` with `use_pca=True` to reduce dimensionality via SVD-based PCA before pgvector insertion.
- Set `table_name` if the Supabase table name differs from the default `signal_fingerprints`.

## CLI Examples
- Execute the flow on synthetic data:
  ```bash
  python - <<'PY'
  import numpy as np
  import pandas as pd
  from flows.embeddings_and_fingerprints import EmbedderConfig, fingerprint_vectorization

  df = pd.DataFrame({
      "timestamp": pd.date_range("2024-01-01", periods=4, freq="h"),
      "feature_a": np.linspace(0, 1, 4),
      "feature_b": np.linspace(1, 2, 4),
  })

  configs = [
      EmbedderConfig(
          name="identity",
          callable_path="numpy.identity",  # returns identity matrix; acts as a placeholder
          enabled=False,
      ),
  ]

  result = fingerprint_vectorization(
      asset_symbol="DEMO",
      embedder_configs=configs,
      numeric_features=df,
      feature_columns=["feature_a", "feature_b"],
      metadata_columns=["timestamp"],
      target_dim=4,
  )
  print(result)
  PY
  ```
- Run tests covering the helper utilities: `python -m pytest tests/flows/test_embeddings_and_fingerprints.py`.

## Failure Modes & Retries
- Missing numeric features raise `ValueError` before attempting Supabase writes.
- Dimensionality mismatches across feature blocks raise `ValueError` to surface upstream data issues.
- When Supabase credentials are absent, the flow returns the payload without remote persistence.
- PCA requests with `target_dim <= 0` or insufficient columns trigger descriptive validation errors.

## Validation Checks
- Unit tests under `tests/flows/test_embeddings_and_fingerprints.py` cover payload extraction, concatenation, PCA, embedder execution, and record building.
- Prefect logs should confirm aligned dimension counts and row persistence per execution.
- Optional downstream validation can query `signal_fingerprints` to ensure vector norms and metadata match expectations.
