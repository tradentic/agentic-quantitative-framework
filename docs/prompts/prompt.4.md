# Agent Task: Align schema, flows, and pipeline for insider signals

## GOAL
Ship a cohesive patch that clears the outstanding regressions identified in the latest repo review by:
1. Reconciling Supabase schemas/seeds with the new ingestion/feature flows.
2. Ensuring optional dependencies fail gracefully.
3. Wiring the insider trading pipeline to exercise the new flows end-to-end.

## CONTEXT & SOURCES OF TRUTH
- Global project guidance: `AGENTS.md`
- Existing capability docs (Form 4, FINRA, fingerprints, similarity, backtest) under `docs/capabilities/`
- Schema definition + migrations under `supabase/migrations/`
- Previous review summary (see PR discussion) noting mismatches between flows and tables

## HARD CONSTRAINTS
- ❗ Do **not** modify unrelated files—keep changes scoped to the paths listed below unless absolutely required by failing tests.
- ❗ Preserve existing APIs unless the fix requires a breaking change; document any intentional breaking change in changelog/docs.
- ✅ All seed SQL must live in **`supabase/seed.sql`** (no extra seed files elsewhere).
- ✅ Maintain idempotent migrations (use `create table if not exists`/`alter table` guard rails where needed).
- ✅ Keep tests green; add/extend coverage in colocated `tests/` packages when fixing logic.

---

## 1) Supabase Schema & Seed Alignment
**Files:** `supabase/migrations/*.sql`, `supabase/seed.sql`, `docs/capabilities/schema.md`

- Update migrations so that tables required by the flows contain the necessary columns:
  - `edgar_filings`: include `symbol`, `reporter`, `accession_number`, `filing_date`, `xml_url`, provenance hashes, etc.
  - `insider_transactions`: include transaction-level fields (`accession_number`, `transaction_date`, `transaction_code`, `shares`, `price`, `reporter_cik`, `symbol`).
  - `daily_features`: choose a consistent layout. Either (a) widen the table to have explicit columns (`short_vol_share`, `short_exempt_share`, `ats_share_of_total`) or (b) adapt flows to match a key/value schema. Pick one approach and apply it everywhere.
  - `signal_fingerprints`: ensure required columns (`id`, `signal_name`, `version`, `asset_symbol`, `window_start`, `window_end`, `fingerprint`, `provenance`, `meta`) match the flow payloads.
- If migrations already exist, author additive migrations (e.g., `ALTER TABLE ... ADD COLUMN`) to reach the desired schema—do **not** rewrite history.
- Rework `supabase/seed.sql` to seed coherent demo rows for the updated tables (filings, transactions, features, fingerprints). Remove outdated seed paths; ensure the file can run after a `supabase db reset --local`.
- Refresh `docs/capabilities/schema.md` to describe the revised schemas and the deterministic seed contents.

## 2) Form 4 Flow Persistence Fixes
**Files:** `flows/ingest_sec_form4.py`, `framework/sec_client.py`, `tests/sec/test_sec_client.py`, `docs/capabilities/sec-form4.md`

- Update the flow’s database writes to match the corrected Supabase schema from section 1 (e.g., include `symbol`, `reporter`, `accession_number`, provenance fields).
- Ensure batching/upsert logic handles duplicate filings gracefully and commits without column errors.
- Extend unit tests or add integration-style tests (mocking Supabase client if needed) to assert the flow constructs the exact payload schema expected by the database layer.
- Confirm docs mention the normalized schema and provenance hash behavior.

## 3) FINRA Off-Exchange Feature Flow
**Files:** `flows/compute_offexchange_features.py`, `framework/finra_client.py`, `tests/finra/test_finra_client.py`, `docs/capabilities/finra.md`

- Align the flow’s output structure with the chosen `daily_features` table shape.
  - If using wide columns, update ORM/upsert helpers accordingly.
  - If using key/value storage, adjust the flow to emit multiple rows per feature key.
- Add/adjust tests to cover the new persistence logic and catch schema drift early.
- Update docs to reflect the storage format.

## 4) Optional Dependency Guardrails
**Files:** `features/minirocket_embeddings.py`, `tests/features/test_minirocket.py`, related docs

- Defer heavy imports (`sktime`, etc.) to function scope so importing the module without the extra dependency no longer raises `ModuleNotFoundError`.
- Provide a clear error message when the dependency is missing at call time and adapt tests to mock this behavior (skip when dependency unavailable).
- Document the optional dependency requirement in `docs/capabilities/minirocket.md`.

## 5) Fingerprint Flow & Supabase Contract
**Files:** `flows/embeddings_and_fingerprints.py`, `docs/capabilities/fingerprints.md`, relevant tests under `tests/flows/`

- Update the flow to populate all mandatory columns (`signal_name`, `version`, window bounds, etc.) and ensure the pgvector payload length matches the schema.
- Add validation for provenance metadata (`source_url`, `feature_version`, hashes) before upserts.
- Extend unit/integration tests to assert the assembled payload conforms to the database schema.
- Refresh docs with an example payload and updated contract.

## 6) Insider Trading Pipeline Glue
**Files:** `use_cases/insider_trading/pipeline.py`, `use_cases/insider_trading/config.yaml`, `docs/use-cases/insider_trading.md`, any necessary mocks/tests under `tests/use_cases/`

- Replace placeholder logging with real orchestration that invokes:
  1. SEC ingest (for the requested date range),
  2. FINRA feature computation,
  3. Fingerprint generation,
  4. Similarity scans, and
  5. Backtest execution (for training mode).
- Support `mode` switches (`train`, `score`, `refresh`) with appropriate subsets of the above steps.
- Wire configuration flags so external API calls can be mocked/stubbed during tests.
- Add tests covering at least one pipeline mode with dependency mocks to ensure control flow works.
- Document the end-to-end usage with updated CLI examples.

---

## VERIFICATION CHECKLIST (automate where feasible)
1. `pytest` (or targeted subsets) covering updated modules.
2. `supabase db reset --local` succeeds, applying migrations and running the new `supabase/seed.sql`.
3. Smoke run: `python -m use_cases.insider_trading.pipeline --mode score --date YYYY-MM-DD` completes with mocked vendors.
4. Optional: run the SEC and FINRA flows individually to confirm schema-aligned inserts (log output/screenshots acceptable in docs).

---

## OUTPUT
- Open a PR titled **“Fix Form 4 + FINRA persistence, optional deps, and insider pipeline wiring”** summarizing the six focus areas above.
- Include a changelog/docs note describing the schema adjustments and pipeline wiring.
