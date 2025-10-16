# Coding Agent Prompt — Post-Merge Architecture & Implementation Audit (v1)

You are a coding agent operating **inside the repo’s workspace** (root of the current project). Your task is to **audit the current implementation** after recent merges and provide a rigorous, evidence-backed report. This is a **read-first, write-light** audit: generate reports and sample diffs/PR plans, but **do not** modify code unless explicitly asked in a follow-up task.

---

## Goals

1. **Confirm capability**: Verify the codebase can support advanced feature generation and insider-signals workflows (matrix profile, change-points, Hawkes, microstructure metrics, VPIN, TS embeddings incl. TS2Vec / MiniRocket / DeepLOB, vector fingerprints, Prefect flows, Supabase/pgvector).
2. **Surface gaps**: Identify missing modules, schema objects, flows, or configs; flag misalignments with the intended architecture.
3. **Produce artifacts**: Create concise, navigable reports (markdown + JSON) with command outputs and file inventories that I can review.
4. **List asks**: Provide specific questions/inputs needed from the user (e.g., secrets, vendor creds, example dates/symbols) for deeper runs.

---

## Non-Destructive Policy

* Default to **read-only** operations. Use dry-runs and local checks. Do **not** deploy or mutate production data.
* If a command would write to DB/files, isolate under `reports/audit/` or use `--dry-run` flags. Avoid network calls that incur cost.

---

## Expected Project Layout (flexible)

* `features/` — feature extractors (e.g., `matrix_profile.py`, `change_points.py`, `hawkes_features.py`, `microstructure.py`, `vpin.py`, `minirocket_embeddings.py`, `deeplob_embeddings.py`, `generate_ts2vec_embeddings.py`).
* `framework/` — data clients (`sec_client.py`, `finra_client.py`, `vendor_markets.py`), supabase client, utilities.
* `flows/` — Prefect flows (`ingest_sec_form4.py`, `compute_offexchange_features.py`, `compute_intraday_features.py`, `embeddings_and_fingerprints.py`, `similarity_scans.py`, `backtest.py`).
* `agents/` — tool wiring, LangGraph chain setup, orchestration helpers.
* `supabase/` — migrations, seeds, SQL RPCs (tables: `edgar_filings`, `insider_transactions`, `daily_features`, `signal_fingerprints`).
* `use_cases/insider_trading/` — glue pipeline (`pipeline.py`), configs.
* `prefect.yaml` — deployments and parameters.

> If the structure differs, auto-discover actual paths and map them to the roles above.

---

## Inputs & Secrets (request only if needed)

If a step requires external access, collect but **do not print** secrets:

* `SUPABASE_URL`, `SUPABASE_ANON_KEY` or service key, `DATABASE_URL`
* Market data vendor keys (e.g., Polygon), EDGAR throttle config, FINRA endpoints
* Optional GPU flag for DeepLOB
  List any missing values in **Questions Needed** at the end of your report.

---

## Deliverables (write to repo—non-intrusive)

Create a timestamped folder: `reports/audit/YYYYMMDD_HHMM/` and generate:

1. `AUDIT.md` — human-readable report (see template below)
2. `AUDIT.json` — machine-readable summary (schema below)
3. `FEATURE_INVENTORY.md` — discovered feature modules & signatures
4. `SCHEMA_CHECK.md` — DB objects found/missing; pgvector status
5. `FLOWS_CHECK.md` — Prefect deployments & flow entrypoints
6. `CAPABILITY_MATRIX.md` — ✅/⚠️/❌ by capability vs implementation
7. `PATCH_PLAN.md` — minimal PR plan to close gaps (grouped by component)
8. `QUESTIONS.md` — consolidated questions & next data needed

Also output a short **console summary** at the end of your run.

---

## Allowed Tools & Commands

* Python (installed project + dev deps), `pytest -q`, `ruff`, `mypy` if present
* Prefect CLI: `prefect version`, `prefect deployments ls`, `prefect config view`
* Git commands: `git status`, `git rev-parse --short HEAD`, `git branch --show-current`
* Supabase CLI (if available locally): `supabase status`, `supabase db reset --local` (use **dry-run** if possible)
* SQL checks via `psql`/driver (read-only): check extensions, tables, columns
* File system introspection (`tree`, `ls -R`, glob scans)

> If a tool is missing, note it and continue with alternate static checks.

---

## Step-by-Step Procedure

### 1) Repository Scan & Identity

* Print: repo root, current branch, commit SHA, dirty state
* Inventory top-level dirs, key files (`README*`, `prefect.yaml`, `.env*`, `pyproject.toml`, `requirements*`)

### 2) Feature Inventory

* Enumerate `features/*.py`. For each module, extract callable entrypoints (e.g., `compute(window, df, cfg)`), docstrings, and emitted columns/embedding dims.
* Expected set: `matrix_profile`, `change_points`, `hawkes_features`, `microstructure`, `vpin`, `generate_ts2vec_embeddings`, `minirocket_embeddings`, `deeplob_embeddings`.
* Output: `FEATURE_INVENTORY.md` with a matrix: **present?**, **imports OK?**, **deps installed?**, **unit smoke?**

### 3) Agents & Tools Wiring

* Inspect `agents/` for LangGraph / tool bindings: confirm tools for Supabase, SEC, FINRA, vendor markets, vector search, flows triggering.
* Note missing bindings or unused modules.

### 4) Flows & Deployments

* Read `prefect.yaml`; list deployments, parameters, schedules.
* Static-parse `flows/*.py` for `@flow` entrypoints and parameter signatures.
* If Prefect CLI available: `prefect deployments ls` (capture table). No runs—**list only**.

### 5) Supabase / DB Schema Checks (read-only)

* Confirm presence of migrations/seeds under `supabase/`.
* If local DB accessible: verify `CREATE EXTENSION IF NOT EXISTS vector;`
* Check tables & key columns:

  * `edgar_filings` (keys, indexes, provenance cols like `source_url`, `xml_sha256`, `parser_version`)
  * `insider_transactions`
  * `daily_features` (wide numeric, `feature_version`)
  * `signal_fingerprints` (vector column, metadata)
* Record missing objects, wrong types, or absent indexes.

### 6) Static Config Validation

* Gather `.env*` & config templates; list required env vars and defaults.
* Cross-check code references to env vars (grep) vs templates.

### 7) Minimal Smoke (No External IO)

* Import each feature module; run **synthetic** tiny DataFrame through (mocked window) to validate signatures and column names.
* Do **not** call vendors/EDGAR.

### 8) Capability Matrix

* Map findings to these rows: **Vector store**, **TS embeddings**, **MiniRocket**, **DeepLOB**, **Microstructure**, **VPIN**, **Matrix Profile**, **Change-points**, **Hawkes**, **Use-case glue**, **Backtests**, **Similarity scans**, **Provenance**, **Idempotency**.
* Rate each as ✅ present & wired, ⚠️ partial, ❌ missing.

### 9) Patch Plan

* For each ❌/⚠️: provide a **minimal PR** plan (branch name, file paths, function stubs, tests, migration names). Keep unrelated code untouched.

### 10) Questions Needed

* List crisp questions, prioritized by blockers vs nice-to-have.

---

## Output Templates

### `AUDIT.md`

**Repo**: `<name>`
**Branch/SHA**: `<branch> @ <sha>`

### Summary

* One-paragraph overview with top 5 findings.

### Architecture Parity

* Table mapping intended components → actual paths/files; notes on deviations.

### Capability Matrix

(✅/⚠️/❌ table with brief evidence links to sections below)

### Evidence Sections

1. **Features** — inventory + import tests + synthetic run notes
2. **Agents/Tools** — discovered tool bindings, gaps
3. **Flows** — `prefect.yaml` and discovered `@flow` entrypoints
4. **Database** — schema objects & pgvector status
5. **Config** — env vars, sample `.env` completeness
6. **Provenance/Idempotency** — presence of versioning/hash cols & upsert logic

### Patch Plan (Condensed)

* Bullet list of minimal, isolated PRs with scope & acceptance tests

### Questions Needed

* Precise list of inputs/secrets/time ranges/symbol sets to proceed with deeper runs

---

### `AUDIT.json` (schema)

```json
{
  "repo": {"name": "string", "branch": "string", "sha": "string"},
  "capabilities": {
    "vector_store": "present|partial|missing",
    "ts2vec": "present|partial|missing",
    "minirocket": "present|partial|missing",
    "deeplob": "present|partial|missing",
    "microstructure": "present|partial|missing",
    "vpin": "present|partial|missing",
    "matrix_profile": "present|partial|missing",
    "change_points": "present|partial|missing",
    "hawkes": "present|partial|missing",
    "backtests": "present|partial|missing",
    "similarity_scans": "present|partial|missing",
    "use_case_glue": "present|partial|missing",
    "provenance": "present|partial|missing",
    "idempotency": "present|partial|missing"
  },
  "features": [{"module": "string", "present": true, "imports_ok": true, "emb_dim": 128, "notes": "string"}],
  "flows": [{"path": "string", "entrypoints": ["string"], "deployed": true}],
  "db": {"pgvector": true, "tables": [{"name": "string", "present": true, "columns": ["..."]}]},
  "questions": ["string", "..."]
}
```

---

## Heuristics & Checks (quick)

* Prefer **imports over execution** for third-party data clients.
* If `prefect.yaml` absent, statically parse function names with `@flow` to infer deployables.
* Verify vector dims consistency (e.g., TS2Vec 128d matches `signal_fingerprints.vector` length).
* Look for provenance columns (`source_url`, `xml_sha256`, `parser_version`, `feature_version`).
* Ensure idempotent upserts (e.g., `ON CONFLICT` keys by `(symbol, ts, feature_version)`).

---

## Success Criteria

* All deliverables written to `reports/audit/<ts>/`.
* `AUDIT.md` contains an executive summary, capability matrix, and actionable PR plan.
* `QUESTIONS.md` lists exact missing inputs to proceed with deeper, data-backed validation.

---

## Final Console Summary (print at end)

* 3–5 bullets summarizing: capability coverage, top gaps, required inputs, and next actions.

---

## Stretch (optional if time allows)

* Generate **sample diffs** in `patches/` as `.diff` files for each proposed PR, touching the **minimum** lines.
* Emit a tiny Python script in `scripts/audit_feature_dims.py` that verifies embedding dims vs DB schema.

> Proceed with the audit now. Keep it deterministic and reproducible. Do **not** change unrelated code. Collect evidence and write the reports listed above.
