# Patch Plan

## 1. Stabilise MiniRocket Embeddings
- **Branch**: `fix/minirocket-numpy2`
- **Scope**: `features/minirocket_embeddings.py`, add regression test in `tests/features/test_minirocket.py`.
- **Changes**:
  - Replace `np.float_` annotations with `np.float64`/`float` compat layer for NumPy 2.0.
  - Gate optional `sktime` import inside helper to avoid eager AttributeError.
  - Add smoke test using small synthetic panel (skip when `sktime` missing).
- **Acceptance**: `pytest tests/features/test_minirocket.py` passes locally with `sktime` installed.

## 2. Add Deterministic Embedding Upserts
- **Branch**: `feat/embedding-upsert-keys`
- **Scope**: `framework/supabase_client.py`, `supabase/migrations/*` (new migration), plus tests if available.
- **Changes**:
  - Introduce deterministic UUID (e.g., namespace uuid5) or compute conflict key `(asset_symbol, time_range)`.
  - Update `signal_embeddings` table with unique constraint to support upsert.
  - Adjust `insert_embeddings` to upsert on the new constraint and avoid duplicates.
- **Acceptance**: Unit smoke (if any) plus Supabase migration applying cleanly (`supabase db lint` dry-run).

## 3. Matrix Profile Runtime Guard
- **Branch**: `fix/matrix-profile-stumpy`
- **Scope**: `features/matrix_profile.py`, tests under `tests/features/`.
- **Changes**:
  - Detect absence of `stumpy` or Numba compilation errors and fall back to a CPU-safe algorithm (e.g., `stumpy.stump` with `ignore_warnings=True` or use `stumpy.gpu_stump` flag toggled off).
  - Cache compiled functions or expose `engine="naive"` parameter to bypass heavy compile during smoke tests.
  - Document performance caveats in module docstring.
- **Acceptance**: Synthetic unit test completes within CI time (no manual interruption required).

## 4. Document Data Contracts for Microstructure / VPIN
- **Branch**: `docs/microstructure-contract`
- **Scope**: `features/microstructure.py`, `features/vpin.py`, `docs/` (new README section).
- **Changes**:
  - Expand docstrings/comments outlining required columns (`timestamp`, `size`, etc.).
  - Provide example usage in documentation and optionally helper to coerce raw data.
- **Acceptance**: Documentation build (if any) plus lint passes.

## 5. DeepLOB Asset Packaging (Optional)
- **Branch**: `feat/deeplob-artifacts`
- **Scope**: `features/deeplob_embeddings.py`, `docs/`, add config under `use_cases` if needed.
- **Changes**:
  - Provide configuration for loading pretrained weights (path/env var) and clarify GPU toggle.
  - Add guard raising descriptive error when weights missing.
- **Acceptance**: Smoke script demonstrating CPU inference with dummy weights.
