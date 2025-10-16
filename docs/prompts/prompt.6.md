# Coding Agent Prompt — Post‑Audit Fixes (v1)

You are a coding agent operating **inside this repository** at the repo root. Your job is to **apply the smallest safe patches** to resolve issues flagged by the audit bundle under `reports/audit/20251016_1906/`. Work in **small branches**, add tests, and avoid touching unrelated code. Prefer additive changes and explicit migrations.

> **Prime directive:** Keep changes minimal, deterministic, and reversible. Where behavior changes, add clear migrations, guards, and tests.

---

## Targets (from the audit)

1. **MiniRocket import failure (NumPy ≥ 2.0)** and large output dimensionality.
2. **Idempotency gaps** (missing `UNIQUE` + `UPSERT`) for vector writes.
3. **Matrix‑Profile runtime guard** (avoid JIT stalls / provide CPU‑safe fallback).
4. **Prefect deployment drift** (entrypoint mismatch for `compute-intraday`).
5. **Embedding dimension discipline** (single canonical fingerprint size + runtime checks).
6. **Microstructure/VPIN data contracts** (columns/types/units doc + smoke checks).
7. **DeepLOB weights path & CPU fallback** (config + graceful degrade).
8. **CI validations** (embedding dim vs DB schema; deployment/flow parity).

---

## Branch plan (one PR each)

### 1) `fix/minirocket-numpy2`

**Goal:** Make MiniRocket import robust under NumPy ≥ 2.0; keep framework runnable when `sktime` missing.

**Changes**

* `features/minirocket_embeddings.py`:

  * Replace removed NumPy aliases (`np.float`, `np.float_`, `np.int`) with standard types (`float`/`np.float64`, `int`).
  * Guard imports:

    ```python
    try:
        from sktime.transformations.panel.rocket import MiniRocketMultivariate as MiniRocket
        SKTIME_AVAILABLE = True
    except Exception as e:
        SKTIME_AVAILABLE = False
        IMPORT_ERR = e
    ```
  * If `SKTIME_AVAILABLE` is False, log a clear warning and raise a controlled `DependencyUnavailable("sktime/MiniRocket not installed")` **only** when this extractor is invoked.
* Add `tests/features/test_minirocket_import.py` with:

  * Import smoke test.
  * Skip test if `SKTIME_AVAILABLE` is False.

**Acceptance**

* `pytest -q` green.
* The rest of the framework runs even when `sktime` isn’t installed.

---

### 2) `feat/embeddings-fingerprint-pca-128`

**Goal:** Standardize canonical fingerprint vectors to **128 dims** and safely fit/transform high‑dim embeddings (e.g., MiniRocket) via PCA.

**Changes**

* New module `features/pca_fingerprint.py`:

  * `fit_pca(X, n_components=128, random_state=42) -> PCAModel`
  * `transform_pca(model, X) -> ndarray[*,128]`
  * Save/load PCA model to `artifacts/pca/minirocket_128.pkl` (use `joblib`).
* Update the embedding pipeline to:

  * Generate raw MiniRocket features (often ~10k dims).
  * Fit PCA **once** per extractor/version (`feature_version`), persist the model, then transform to 128‑d.
  * Write only the 128‑d **fingerprint** into `signal_fingerprints.fvec`.
* Add runtime guard before insert: `assert vec.shape[-1] == 128`.
* Create `scripts/audit_vector_dims.py` that verifies DB column dim vs produced vectors.

**DB (migration)**

* If needed, adjust column to 128 dims:

  * `supabase/migrations/20251016_fingerprints_vector_128.sql`:

    ```sql
    -- ensure pgvector
    create extension if not exists vector;

    -- ensure column is vector(128)
    alter table if exists signal_fingerprints
      alter column fvec type vector(128)
      using fvec;
    ```

**Acceptance**

* `scripts/audit_vector_dims.py` reports 100% conformity.
* Inserting MiniRocket fingerprints yields `vector(128)` with no runtime errors.

---

### 3) `chore/db-idempotent-upserts`

**Goal:** Enforce uniqueness + idempotent writes for daily features and fingerprints.

**DB (migration)** `supabase/migrations/20251016_idempotency.sql`:

```sql
-- daily features unique identity
alter table if exists daily_features
  add column if not exists feature_version text not null default 'v1';
create unique index if not exists daily_features_uniq
  on daily_features(symbol, trade_date, feature_version);

-- fingerprints unique identity
alter table if exists signal_fingerprints
  add column if not exists version text not null default 'v1';
create unique index if not exists signal_fingerprints_uniq
  on signal_fingerprints(asset_symbol, window_start, window_end, version);
```

**Client changes**

* Update writers to use UPSERT:

  ```sql
  insert into signal_fingerprints(...)
  values (...)
  on conflict (asset_symbol, window_start, window_end, version)
  do update set fvec = excluded.fvec, updated_at = now();
  ```

**Acceptance**

* Re‑running the same flow produces **no duplicates**; rows update in place.

---

### 4) `fix/prefect-entrypoints`

**Goal:** Align deployment names, entrypoints, and `@flow` functions.

**Changes**

* In `prefect.yaml`, ensure:

  * `compute-intraday` → `entrypoint: flows/compute_intraday_features.py:compute_intraday_features`
  * Each deployment `name` ≈ snake‑to‑kebab of the function name.
* Add `tests/flows/test_entrypoints.py` that parses `prefect.yaml` and imports referenced flow functions.

**Acceptance**

* `prefect deployments ls` lists the corrected deployments; `tests/flows/test_entrypoints.py` passes.

---

### 5) `feat/matrix-profile-guard`

**Goal:** Avoid numba/JIT stalls and provide deterministic CPU fallback.

**Changes**

* `features/matrix_profile.py`:

  * Add `engine` param: `"numba"|"naive"` with default from env `MATRIX_PROFILE_ENGINE`.
  * If numba path fails or env sets `naive`, use naive engine; log the chosen path.
* Add `tests/features/test_matrix_profile.py` with a tiny synthetic series to exercise both paths.

**Acceptance**

* Both engines produce consistent scalar features (within tolerance) on the synthetic dataset.

---

### 6) `docs/feature-data-contracts`

**Goal:** Lock column names/types/units for Microstructure & VPIN features.

**Changes**

* New doc `docs/specs/FEATURE_CONTRACTS.md` describing:

  * Microstructure columns: `ofi_l1`, `ofi_l5`, `imbalance_l1`, `eff_spread_bps`, `realized_spread_bps`, `kyle_lambda`, `amihud_illiq`, etc.; units & windowing.
  * VPIN columns: `vpin`, `vpin_delta`, `bucket_size`, `window_mins`.
* Add smoke tests validating schema (column presence + dtype) in `tests/features/test_contracts.py`.

**Acceptance**

* Contract tests pass; downstream training notebooks see stable column names.

---

### 7) `feat/deeplob-assets-fallback`

**Goal:** Make DeepLOB optional, with configurable weights and CPU fallback.

**Changes**

* `features/deeplob_embeddings.py`:

  * Read `DEEPLOB_WEIGHTS_PATH`/`DEEPLOB_DEVICE` from env.
  * If weights missing or GPU unavailable, log and skip with a controlled error **only when used**.
* Add `tests/features/test_deeplob_import.py` with skip-on-missing‑weights behavior.

**Acceptance**

* Import no longer breaks the repo; when configured, a tiny synthetic forward pass returns 64‑d embeddings.

---

### 8) `ops/ci-validations`

**Goal:** Prevent regressions.

**Changes**

* Add CI job `ci/validate-embeddings.yml` to run `scripts/audit_vector_dims.py`.
* Add `ci/validate-prefect.yml` to import referenced flows from `prefect.yaml`.
* Add pre‑commit hooks for `ruff`/`black` (if present) and `pytest -q`.

**Acceptance**

* CI red if dims mismatch DB or a deployment references a missing flow.

---

## Commands (local, non‑destructive)

```bash
# env
cp .env.example .env

# run tests
pytest -q

# Prefect check (no runs)
prefect version
prefect deployments ls || true

# Supabase (local)
supabase start
supabase db reset --local

# Dim audit
python scripts/audit_vector_dims.py
```

---

## Commit messages (examples)

* `fix(features): MiniRocket import compatibility with NumPy 2.0; gate sktime`
* `feat(embeddings): PCA→128 canonical fingerprints + runtime dim guard`
* `chore(db): add UNIQUE+UPSERT for daily_features and signal_fingerprints`
* `fix(flows): correct compute-intraday entrypoint + flow-import test`
* `feat(features): matrix-profile naive fallback + tests`
* `docs(features): data contracts for microstructure & VPIN`
* `feat(features): DeepLOB weights path + CPU fallback`
* `ci: add embedding-dim and prefect-entrypoint validations`

---

## Acceptance checklist (end-to-end)

* [ ] `pytest -q` passes; MiniRocket and Matrix‑Profile tests behave deterministically.
* [ ] `supabase db reset --local` creates vector tables and constraints; UPSERTs work.
* [ ] `scripts/audit_vector_dims.py` shows **128/128** compliance for fingerprints.
* [ ] `prefect deployments ls` lists all corrected deployments without import errors.
* [ ] A sample run (symbol/date window) writes **one** fingerprint per window (re‑runs update in place).

---

## Notes

* Keep all heavy/raw embeddings (e.g., full MiniRocket) out of the canonical fingerprint column; only store the 128‑d PCA outputs there.
* If you later need larger dims, add a separate table or consider quantization/half‑precision; do not silently change `vector(128)` without a migration + tests.

> Proceed with these branches in order: (1) idempotent upserts, (2) MiniRocket fix, (3) PCA‑128 fingerprints, (4) Prefect entrypoint fix, then the rest. Ensure each PR is reviewable and green in CI before merging.
