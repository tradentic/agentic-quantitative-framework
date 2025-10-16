# Insider Signals — Capability Prompts (Self‑Contained, One‑Per‑Feature)

> Drop‑in Markdown prompts you can paste into your coding agent. Each prompt is **self‑contained**, scoped, and says **“Do not modify unrelated files.”** They assume your monorepo uses: Python, LangGraph/LangChain agents, Prefect 2.x for orchestration, Supabase/Postgres (+pgvector) for storage. If a path already exists, the agent must **append** or create new files beside it without touching unrelated code.

**Index**

1. [SEC Form 4 Ingest](#1-sec-form-4-ingest-frameworksec_clientpy--flowsingest_sec_form4py)
2. [Market Vendor (NBBO/Trades)](#2-market-vendor-nbbotrades-frameworkvendor_marketspy)
3. [FINRA Short & ATS](#3-finra-short--ats-frameworkfinra_clientpy--flowscompute_offexchange_featurespy)
4. [Microstructure Features](#4-microstructure-features-featuresmicrostructurepy)
5. [Matrix Profile](#5-matrix-profile-featuresmatrix_profilepy)
6. [Change‑Points](#6-change-points-featureschange_pointspy)
7. [Hawkes Features](#7-hawkes-features-featureshawkes_featurespy)
8. [VPIN Features](#8-vpin-features-featuresvpinpy)
9. [MiniRocket Embeddings](#9-minirocket-embeddings-featuresminirocket_embeddingspy)
10. [DeepLOB Embeddings](#10-deeplob-embeddings-featuresdeeplob_embeddingspy)
11. [Supabase Schema + Seeds](#11-supabase-schema--seeds-supabasemigrations--sqlseeds)
12. [Embeddings→Fingerprints Flow](#12-embeddings→fingerprints-flow-flowsembeddings_and_fingerprintspy)
13. [Similarity Scans Flow](#13-similarity-scans-flow-flowssimilarity_scanspy)
14. [Backtest Flow](#14-backtest-flow-flowsbacktestpy)
15. [Insider Trading Use‑Case Glue](#15-insider-trading-use-case-glue-use_casesinsider_trading)
16. [Prefect Deployments](#16-prefect-deployments-prefectyaml)
17. [Observability & Provenance](#17-observability--provenance-logging-checksums)

---

## 1) SEC Form 4 Ingest (`framework/sec_client.py` + `flows/ingest_sec_form4.py`)

**Prompt — paste into your coding agent**

**Title:** Implement deterministic SEC Form 4 ingest (daily index + XML parser)

**Objective:** Create a back‑fillable, deterministic Form 4 ingestion client and a Prefect flow to populate `edgar_filings` and `insider_transactions` without touching unrelated code.

**Constraints**

* Do **not** modify unrelated files.
* Use only the files/paths listed below.
* Add unit tests colocated under `tests/sec/`.

**New/Updated Files**

* `framework/sec_client.py` (NEW)
* `flows/ingest_sec_form4.py` (NEW)
* `tests/sec/test_sec_client.py` (NEW)
* `docs/capabilities/sec-form4.md` (NEW)

**Implementation**

1. `framework/sec_client.py`

   * Functions:

     * `daily_index_urls(date: date) -> list[str]`
     * `iter_form4_index(date: date) -> Iterator[Form4IndexRow]`
     * `accession_to_primary_xml_url(acc_path: str) -> str`
     * `parse_form4_xml(xml_bytes: bytes) -> ParsedForm4` with fields: symbol, transactions[{date, code, shares, price}], reporter, cik, accession.
   * Include `User-Agent` header support and simple retry.
2. `flows/ingest_sec_form4.py`

   * Prefect flow `ingest_form4(date_from, date_to)` that:

     * Iterates daily indices, fetches XML, parses, and upserts into `edgar_filings`, `insider_transactions`.
   * Log counts; commit in batches.
3. `tests/sec/test_sec_client.py` with small frozen fixtures.
4. `docs/capabilities/sec-form4.md` docs: data contract, rate‑limiting, retry/backoff, and provenance.

**Acceptance**

* Running `python -m flows.ingest_sec_form4 --date 2024-12-31` inserts rows.
* Unit tests pass.

**Branch/Commit**

* Branch: `feat/sec-form4-ingest`
* Commit: `feat(sec): deterministic Form 4 ingest + flow + docs`

---

## 2) Market Vendor (NBBO/Trades) (`framework/vendor_markets.py`)

**Title:** Add pluggable NBBO/Trades client

**Objective:** A single adapter that fetches trades & quotes for a symbol/date window; returns tidy DataFrames for downstream features.

**Files**

* `framework/vendor_markets.py` (NEW)
* `tests/market/test_vendor_markets.py` (NEW)
* `docs/capabilities/vendor-markets.md` (NEW)

**Implementation**

* Abstract interface: `get_trades(symbol, start, end)`, `get_nbbo(symbol, start, end)`.
* Implement `PolygonClient` behind env flags; no secrets committed.
* Normalize schema: timezone aware, condition codes, exchange/venue, is_off_exchange flag if available.

**Acceptance**

* Smoke test fetch for a tiny window; returns non‑empty frames with canonical columns.

**Branch:** `feat/vendor-markets-adapter`

---

## 3) FINRA Short & ATS (`framework/finra_client.py` + `flows/compute_offexchange_features.py`)

**Title:** FINRA short volume + ATS weekly joins

**Objective:** Pull daily short volume and weekly ATS aggregates, align to symbol‑day features.

**Files**

* `framework/finra_client.py` (NEW)
* `flows/compute_offexchange_features.py` (NEW)
* `tests/finra/test_finra_client.py` (NEW)
* `docs/capabilities/finra.md` (NEW)

**Implementation**

* Client: `get_short_volume(symbol, date)`, `get_ats_week(symbol, week_ending)`.
* Flow: daily job that fills `daily_features` columns: `short_vol_share`, `short_exempt_share`, `ats_share_of_total`.

**Acceptance**

* Backfills a sample month without errors; idempotent.

**Branch:** `feat/finra-offexchange`

---

## 4) Microstructure Features (`features/microstructure.py`)

**Title:** OFI, book imbalance, Kyle’s λ, Amihud ILLIQ, spreads

**Objective:** Compute robust microstructure metrics from trades+NBBO windows.

**Files**

* `features/microstructure.py` (NEW)
* `tests/features/test_microstructure.py` (NEW)
* `docs/capabilities/microstructure.md` (NEW)

**Implementation**

* Functions: `compute_ofi(quotes)`, `book_imbalance(quotes)`, `kyle_lambda(trades, nbbo)`, `amihud_illiq(trades)`, `spreads(nbbo)`.
* Return a single row per (symbol,date,window) with numeric fields and QC flags.

**Acceptance**

* Unit tests on synthetic books validate signs and ranges.

**Branch:** `feat/microstructure-features`

---

## 5) Matrix Profile (`features/matrix_profile.py`)

**Title:** Shape‑anomaly metrics via Matrix Profile

**Objective:** For any series (volume, spread, off‑exchange share), compute discord distance and motif counts per window.

**Files**

* `features/matrix_profile.py` (NEW)
* `tests/features/test_matrix_profile.py` (NEW)
* `docs/capabilities/matrix-profile.md` (NEW)

**Implementation**

* Use `stumpy` for MP; parameters m (subsequence length), k (motifs), return: `discord_dist`, `motif1_dist`, counts.

**Acceptance:** Unit tests on seeded series.

**Branch:** `feat/matrix-profile`

---

## 6) Change‑Points (`features/change_points.py`)

**Title:** Change‑point scores (ruptures + BOCPD)

**Objective:** Detect structural breaks in level/volatility; return scores and deltas.

**Files**

* `features/change_points.py` (NEW)
* `tests/features/test_change_points.py` (NEW)
* `docs/capabilities/change-points.md` (NEW)

**Implementation**

* `ruptures` offline detectors (Pelt/CostL2) and optional BOCPD online wrapper.

**Acceptance:** Reproduces expected breakpoints on synthetic step‑changes.

**Branch:** `feat/change-points`

---

## 7) Hawkes Features (`features/hawkes_features.py`)

**Title:** Hawkes self‑excitation metrics

**Objective:** Fit Hawkes on event streams (orders, cancels, trades) and expose branching ratio & kernel norms.

**Files**

* `features/hawkes_features.py` (NEW)
* `tests/features/test_hawkes.py` (NEW)
* `docs/capabilities/hawkes.md` (NEW)

**Implementation**

* `tick.hawkes` (or stub if no L2); accept generic timestamp lists; return metrics per window.

**Acceptance:** Unit test with simulated Hawkes arrivals recovers >0 branching.

**Branch:** `feat/hawkes-features`

---

## 8) VPIN Features (`features/vpin.py`)

**Title:** VPIN / flow toxicity

**Objective:** Compute VPIN on volume‑bars; return level and ΔVPIN near filing windows.

**Files**

* `features/vpin.py` (NEW)
* `tests/features/test_vpin.py` (NEW)
* `docs/capabilities/vpin.md` (NEW)

**Implementation**

* Volume‑synchronized bars, order‑sign proxy (tick rule), rolling imbalance; export `vpin`, `vpin_change`.

**Acceptance:** Synthetic imbalance yields elevated VPIN.

**Branch:** `feat/vpin`

---

## 9) MiniRocket Embeddings (`features/minirocket_embeddings.py`)

**Title:** Fast time‑series embeddings via MiniRocket

**Objective:** Produce fixed‑length embedding vectors for any numeric panel window.

**Files**

* `features/minirocket_embeddings.py` (NEW)
* `tests/features/test_minirocket.py` (NEW)
* `docs/capabilities/minirocket.md` (NEW)

**Implementation**

* Use `sktime`/`minirocket`; output `np.ndarray` → list[float]; configurable length.

**Acceptance:** Deterministic shape, stable across runs with fixed seed.

**Branch:** `feat/minirocket-embeddings`

---

## 10) DeepLOB Embeddings (`features/deeplob_embeddings.py`)

**Title:** LOB representation via DeepLOB

**Objective:** Provide penultimate‑layer embeddings for LOB snapshots (optional GPU).

**Files**

* `features/deeplob_embeddings.py` (NEW)
* `tests/features/test_deeplob.py` (NEW)
* `docs/capabilities/deeplob.md` (NEW)

**Implementation**

* Lightweight PyTorch model loader; CPU fallback; batch inference; return vector per window.

**Acceptance:** Unit test with random book tensors returns vectors of expected dim.

**Branch:** `feat/deeplob-embeddings`

---

## 11) Supabase Schema & Seeds (`supabase/migrations` + `sql/seeds`)

**Title:** DDL for filings, features, fingerprints + seed row

**Objective:** Create migrations for core tables and a seed script with a valid 128‑dim vector row.

**Files**

* `supabase/migrations/2025xxxx_core_schema.sql` (NEW)
* `sql/seed_vector.sql` (NEW)
* `docs/capabilities/schema.md` (NEW)

**Implementation**

* Tables: `edgar_filings`, `insider_transactions`, `daily_features`, `signal_fingerprints(vector)`, `text_chunks(embedding)`.
* Seed: one demo `signal_fingerprints` row with 128‑dim vector.

**Acceptance:** `supabase db reset --local` applies successfully and seeds 1 row.

**Branch:** `feat/schema-and-seed`

---

## 12) Embeddings→Fingerprints Flow (`flows/embeddings_and_fingerprints.py`)

**Title:** Vectorize and persist fingerprint vectors

**Objective:** Compose enabled embedders and numeric features into a single pgvector row with metadata.

**Files**

* `flows/embeddings_and_fingerprints.py` (NEW)
* `docs/capabilities/fingerprints.md` (NEW)

**Implementation**

* Load configured embedders (TS2Vec/MiniRocket/DeepLOB), concat with numeric features (microstructure, VPIN, etc.), optional PCA to target dim, upsert into `signal_fingerprints` with provenance.

**Acceptance:** Flow runs end‑to‑end on a sample day and writes vectors.

**Branch:** `feat/fingerprints-flow`

---

## 13) Similarity Scans Flow (`flows/similarity_scans.py`)

**Title:** k‑NN scans over `signal_fingerprints`

**Objective:** For a given (symbol, window) vector, return top‑k similar past windows and dump a report.

**Files**

* `flows/similarity_scans.py` (NEW)
* `docs/capabilities/similarity.md` (NEW)

**Implementation**

* Cosine/dot similarity via pgvector; produce CSV/Markdown report with links back to provenance.

**Acceptance:** CLI run outputs top‑k IDs with scores.

**Branch:** `feat/similarity-flow`

---

## 14) Backtest Flow (`flows/backtest.py`)

**Title:** Insider pre‑filing classifier backtest

**Objective:** Weak‑label positives when Form‑4 occurs within T days after a window; evaluate models.

**Files**

* `flows/backtest.py` (NEW)
* `docs/capabilities/backtest.md` (NEW)

**Implementation**

* Label builder; train/val split by time; baseline models (XGB/LightGBM); metrics + calibration; write `reports/backtests/`.

**Acceptance:** Produces metrics JSON + plots; deterministic splits.

**Branch:** `feat/backtest-flow`

---

## 15) Insider Trading Use‑Case Glue (`use_cases/insider_trading`)

**Title:** Glue pipeline & config

**Objective:** One place to wire SEC ingest → market features → embeddings → fingerprints → scans → backtest.

**Files**

* `use_cases/insider_trading/pipeline.py` (NEW)
* `use_cases/insider_trading/config.yaml` (NEW)
* `docs/use-cases/insider_trading.md` (NEW)

**Implementation**

* Pipeline with `mode: {train, score, refresh}`; read `config.yaml` to enable/disable modules.

**Acceptance:** `python -m use_cases.insider_trading.pipeline --mode score --date 2025-01-15` runs end‑to‑end (mocks allowed for vendor calls).

**Branch:** `feat/insider-usecase`

---

## 16) Prefect Deployments (`prefect.yaml`)

**Title:** Register the new flows as deployments

**Objective:** Add non‑intrusive entries for the new flows without altering existing deployment semantics.

**Files**

* `prefect.yaml` (UPDATE — append only)
* `docs/capabilities/prefect.md` (NEW)

**Implementation**

* Add deployments: `ingest-sec-form4`, `compute-offexchange`, `compute-intraday`, `fingerprints`, `similarity-scans`, `backtest` with sensible schedules (cron commented by default).

**Acceptance:** `prefect deploy` lists new deployments; can run locally.

**Branch:** `chore/prefect-deployments`

---

## 17) Observability & Provenance (logging, checksums)

**Title:** Provenance & auditability

**Objective:** Ensure every artifact carries hashes, schema/version tags, and fetch timestamps.

**Files**

* `framework/provenance.py` (NEW)
* `docs/capabilities/provenance.md` (NEW)

**Implementation**

* Helpers: `hash_bytes()`, `record_provenance(table, pk, meta: JSONB)`; decorate flows to persist `source_url`, `xml_sha256`, `parser_version`, `feature_version`.

**Acceptance:** Inserts provenance rows alongside core tables; visible in reports.

**Branch:** `feat/provenance`

---

### Global Rules (apply to all prompts)

* **Do not modify unrelated lines or files.**
* New code must be typed, documented, and unit‑tested where indicated.
* Use environment variables for secrets; no secrets in code.
* Prefer small pure functions; keep flows thin and composable.
* Include README snippets inside each `docs/capabilities/*.md` describing: motivation, inputs/outputs, configs, CLI examples, failure modes, and validation checks.
