# Documentation Index

This repository's documentation lives in the `docs/` directory, which is rendered by Docusaurus.
This README highlights operational tasks relevant to vector fingerprints.

## Fingerprint PCA Artifact

Canonical signal fingerprints are projected to **128 dimensions** using a shared PCA reducer.
The persisted artifact lives at `artifacts/pca/minirocket_128.pkl` and must be refreshed when the
underlying feature distribution drifts. You can train or update the reducer with the utilities in
`features/pca_fingerprint.py`.

```
python -m features.pca_fingerprint  # see module docstrings for helper usage
```

## Auditing Fingerprint Dimensions

Use the CLI script to confirm both the PCA artifact and Supabase fingerprints remain 128-dimensional:

```
python scripts/audit_vector_dims.py --artifact-path artifacts/pca/minirocket_128.pkl
```

The script loads the PCA artifact when present and inspects `signal_fingerprints` rows via Supabase,
raising an error if any stored vectors deviate from the canonical width.
