# Coding Agent Prompt — Post‑Fix Verification Audit (v3)

You are a coding agent operating **inside this repository** at the repo root. The previous PR set addressed: provenance table, idempotent embeddings, Prefect entrypoints, NumPy≥2.0 compatibility, PCA→128 fingerprints, Matrix‑Profile fallback, DeepLOB optionality, feature data contracts, and CI validators. Your job now is to **verify those fixes actually work end‑to‑end** and produce a concise, evidence‑backed report.

> **Prime directive:** Read‑first, write‑light. Use synthetic data and transactions wherever possible. If a step would write to persistent tables, wrap it in a transaction and roll back, or insert & delete the specific rows at the end.

---

## What to produce

Create a timestamped folder: `reports/audit/<YYYYMMDD_HHMM>_postfix/` containing:

1. `AUDIT.md` — human summary with top findings
2. `AUDIT.json` — machine summary (schema below)
3. `FEATURE_INVENTORY.md` — discovered feature modules, versions, deps status, sample outputs
4. `SCHEMA_CHECK.md` — DB objects, vector dims, uniqueness & upsert targets
5. `FLOWS_CHECK.md` — Prefect deployments/entrypoints parity & CLI evidence
6. `CAPABILITY_MATRIX.md` — ✅/⚠️/❌ with evidence links
7. `PATCHES_VERIFIED.md` — specific fixes proven by tests (one line per fix)
8. `QUESTIONS.md` — only true blockers for full E2E runs (creds, weights, sample ranges)

Also print a **console summary** (5 bullets: pass/fail of key fixes).

---

## Assumptions & environment

* You can run Python, psql/DB driver, and Prefect CLI locally.
* Use `.env` / `prefect.yaml` at repo root; do **not** print secrets. If a secret is missing, record it in `QUESTIONS.md` and continue static checks.

Recommended variables (read only): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` or `DATABASE_URL`, `DEEPLOB_WEIGHTS_PATH`, `DEEPLOB_DEVICE`, `MATRIX_PROFILE_ENGINE`.

---

## Step‑by‑step procedure

### 0) Repo identity & config

* Record: repo root, current branch, short SHA, dirty status.
* Inventory: `README*`, `prefect.yaml`, `.env*`, `pyproject.toml`, `requirements*`.
* Parse `.env*` and list **which required vars are present/missing** (do not print values).

### 1) Database & schema checks (read‑only preferred)

* Confirm pgvector extension: `create extension if not exists vector;` already applied.
* Verify core tables exist: `edgar_filings`, `insider_transactions`, `daily_features`, `signal_fingerprints`, `signal_embeddings`, `provenance_events`.
* Confirm vector dims via system catalog:

  ```sql
  -- vector type string for column
  select attname, format_type(atttypid, atttypmod) as type
  from pg_attribute
  where attrelid = 'signal_embeddings'::regclass and attname in ('vec');
  ```

  Expect `vector(128)`.
* Check uniqueness & upsert targets:

  ```sql
  -- daily_features unique identity
  select indexdef from pg_indexes
  where tablename='daily_features' and indexname like '%daily_features_%uniq%';

  -- signal_fingerprints unique identity
  select indexdef from pg_indexes
  where tablename='signal_fingerprints' and indexname like '%signal_fingerprints_%uniq%';

  -- signal_embeddings unique identity
  select indexdef from pg_indexes
  where tablename='signal_embeddings' and indexname like '%signal_embeddings_%uniq%';
  ```
* **Optional transactional smoke** (wrap in a transaction and roll back): insert the same `signal_embeddings` key twice and assert one physical row with updated vector.

### 2) Prefect deployments & entrypoints

* Parse `prefect.yaml` → list deployments with `file.py:function` entrypoints.
* Import every referenced function to ensure it exists.
* Run CLI (no runs): `prefect deployments ls` and capture output.
* Ensure `compute-intraday` maps to `flows/compute_intraday_features.py:compute_intraday_features` and not to off‑exchange.

### 3) Feature modules — imports & synthetic runs

For each module below, import it, print version string/docstring, and run a **tiny synthetic** example:

* `features/matrix_profile.py` — run with `engine='naive'` and (if available) `engine='numba'`; record both outputs and timing.
* `features/change_points.py` — detect a known break in a toy series.
* `features/hawkes_features.py` — if dependency present, fit on a short synthetic event stream; otherwise confirm graceful skip.
* `features/microstructure.py` — given a tiny synthetic trade/quote frame, compute OFI, imbalance, effective/realized spreads.
* `features/vpin.py` — compute `vpin` and `vpin_delta` on a toy sequence.
* `features/generate_ts2vec_embeddings.py` — ensure 128‑d output (or recorded fallback) without external data.
* `features/minirocket_embeddings.py` — verify **NumPy≥2.0 import compatibility** and that, when invoked with `sktime` installed, it returns raw high‑dim features; then confirm PCA→128 pipeline (next step).
* `features/deeplob_embeddings.py` — confirm import never crashes when weights/GPU absent; if weights exist, run one forward pass (64‑d).

Record for each: present? imports_ok? deps? output shape? elapsed time.

### 4) Embedding → Fingerprint discipline

* Confirm the PCA artifact or fitting policy for MiniRocket raw features:

  * If artifact present: load `artifacts/pca/minirocket_128.pkl` and `transform` a synthetic matrix to **128** dims.
  * If not present: fit PCA on synthetic, persist model, transform to **128** dims.
* Run `scripts/audit_vector_dims.py` and capture its summary (expect 100% 128‑d for fingerprints).
* Verify that runtime code asserts dimension conformity before DB writes.

### 5) Provenance logging

* Insert (or dry‑run) a minimal provenance record into `provenance_events` with fields: `source`, `payload` (JSON), `artifact_sha256`, `parser_version`.
* Select back and confirm fields exist; then roll back or delete the record.

### 6) Similarity scan smoke (no external data)

* Construct two or three synthetic 128‑d vectors, insert into `signal_fingerprints` within a transaction, run your k‑NN query path (or SQL function/RPC), confirm ordering by cosine distance, then roll back.

### 7) Capability matrix & regressions checklist

* For each prior red/amber item, mark ✅ only with direct evidence from above steps. Where a dep is optional (DeepLOB, Hawkes), mark ✅‑optional with a note on graceful skip behavior.

---

## `AUDIT.json` schema

```json
{
  "repo": {"branch": "string", "sha": "string", "dirty": true},
  "env": {"needed": ["SUPABASE_URL", "DATABASE_URL", "DEEPLOB_WEIGHTS_PATH", "DEEPLOB_DEVICE"], "present": ["..."], "missing": ["..."]},
  "db": {
    "pgvector": true,
    "tables": [
      {"name": "signal_embeddings", "columns": [{"name": "vec", "type": "vector(128)"}]},
      {"name": "provenance_events", "present": true}
    ],
    "uniqueness": {
      "daily_features": true,
      "signal_fingerprints": true,
      "signal_embeddings": true
    }
  },
  "features": [
    {"module": "matrix_profile", "present": true, "engine_naive": true, "engine_numba": "ok|skipped", "elapsed_ms": 5},
    {"module": "minirocket_embeddings", "numpy2_ok": true, "sktime": "installed|missing", "raw_dim": 10000, "pca_fingerprint_dim": 128}
  ],
  "prefect": {
    "deployments": [{"name": "compute-intraday", "entrypoint": "flows/compute_intraday_features.py:compute_intraday_features", "ls_seen": true}],
    "broken": []
  },
  "fingerprints": {"dim": 128, "audit_pass": true},
  "provenance": {"table": true, "insert_ok": true},
  "capabilities": {
    "vector_store": "present|partial|missing",
    "ts2vec": "present|partial|missing",
    "minirocket": "present|partial|missing",
    "deeplob": "present|optional|missing",
    "microstructure": "present|partial|missing",
    "vpin": "present|partial|missing",
    "matrix_profile": "present|partial|missing",
    "hawkes": "optional|present|missing",
    "similarity_scans": "present|partial|missing",
    "backtests": "present|partial|missing",
    "provenance": "present|partial|missing",
    "idempotency": "present|partial|missing"
  },
  "questions": ["..."],
  "notes": "short free‑text"
}
```

---

## Acceptance criteria (what counts as a pass)

* Vector columns: `signal_embeddings.vec` (or canonical fingerprints) reflect **vector(128)** in the catalog; `scripts/audit_vector_dims.py` reports 100% compliance.
* Idempotency: duplicate insert test on `signal_embeddings` updates in place (no duplicates).
* Prefect: every deployment in `prefect.yaml` resolves to an importable `@flow`; `prefect deployments ls` lists them; `compute-intraday` maps correctly.
* MiniRocket: repo imports clean under NumPy≥2.0; if `sktime` installed, raw features flow through PCA→128; otherwise extractor raises a **controlled** dependency error only when called.
* Matrix‑Profile: `engine='naive'` succeeds; `engine='numba'` either succeeds or is cleanly skipped.
* DeepLOB: import never breaks the repo; optional run works if weights are provided.
* Provenance: `provenance_events` exists; insert/select round‑trip verified.

---

## Failure handling

* If any check fails, record: **What was expected**, **What happened**, **Evidence** (path/trace), and a **1‑line patch plan** in `AUDIT.md` and `PATCHES_VERIFIED.md` (as ❌ with a short suggested PR name).

> Execute these steps now and write the results into `reports/audit/<timestamp>_postfix/`. Keep outputs concise and reproducible. Do not mutate production data; use transactions or clean up after yourself.
