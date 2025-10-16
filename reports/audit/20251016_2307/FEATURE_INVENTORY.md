# Feature Module Inventory

| Module | Key Entrypoints | Present | Imports OK | Synthetic Smoke | Notes |
| --- | --- | --- | --- | --- | --- |
| `features/matrix_profile.py` | `compute_matrix_profile_metrics` | ✅ | ✅ | ✅ | Fallback to naive engine when `stumpy` missing; smoke run returned metrics on toy series. |
| `features/change_points.py` | `change_point_scores` | ✅ | ✅ | ✅ | Offline PELT implementation; BOCPD optional. Smoke run on sine wave produced empty breakpoints as expected for smooth series. |
| `features/hawkes_features.py` | `fit_exponential_hawkes`, `hawkes_self_excitation_metrics` | ✅ | ✅ | ✅ | Handles empty frames and groups; smoke run produced branching ratio + diagnostics for synthetic events. |
| `features/microstructure.py` | `compute_ofi`, `book_imbalance`, `kyle_lambda`, `amihud_illiq`, `spreads` | ✅ | ✅ | ✅ | Requires grouped NBBO/trade data. Synthetic quotes/trades yielded QC-passing metrics. |
| `features/vpin.py` | `compute_vpin` | ✅ | ✅ | ✅ | Volume bar generator implemented; synthetic trades produced VPIN=1.0 with QC pass. |
| `features/generate_ts2vec_embeddings.py` | `generate_ts2vec_features`, `fallback_identity_embeddings` | ✅ | ✅ | ⚠️ | TS2Vec dependency missing; module falls back to identity embeddings padded to 128 dimensions. |
| `features/minirocket_embeddings.py` | `generate_minirocket_embeddings` | ✅ | ⚠️ | ❌ | Optional `sktime` dependency unavailable, raising `DependencyUnavailable`. No local fallback implemented. |
| `features/deeplob_embeddings.py` | `deeplob_embeddings`, `load_deeplob_model` | ✅ | ⚠️ | ❌ | Optional `torch` dependency (and weights) missing; module raises `DependencyUnavailable`. |
| `features/pca_fingerprint.py` | `fit_pca_reducer`, `project_to_fingerprint_width` | ✅ | ✅ | ⚠️ | Requires pre-fit PCA artifact; no smoke executed because artifact absent. Functions enforce 128-dim fingerprints. |
