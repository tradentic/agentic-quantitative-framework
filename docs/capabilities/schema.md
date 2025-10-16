# Supabase Core Schema & Seeds

The insider-trading pipeline persists all normalized data into Supabase. The
latest migrations align the schema with the SEC Form 4, FINRA off-exchange, and
fingerprint flows so that end-to-end orchestration runs without column errors.

## Tables & Columns

### `edgar_filings`
Stores metadata for each Form 4 filing.

| Column | Type | Notes |
| --- | --- | --- |
| `filing_id` | `bigserial` | Primary key. |
| `accession_number` | `text` | Unique accession identifier, upsert target. |
| `cik` | `text` | Issuer CIK from EDGAR. |
| `form_type` | `text` | Form type (`4`, `4/A`). |
| `company_name` | `text` | Issuer name. |
| `filing_date` | `date` | Report date from index. |
| `filed_at` | `date` | Retained for backwards compatibility; mirrors `filing_date`. |
| `symbol` | `text` | Upper-cased issuer trading symbol. |
| `reporter` | `text` | Normalized insider name. |
| `reporter_cik` | `text` | Insider CIK when available. |
| `xml_url` | `text` | Canonical primary XML URL. |
| `payload_sha256` | `text` | Hash of normalized filing payload. |
| `xml_sha256` | `text` | Hash of the downloaded XML bytes. |
| `provenance` | `jsonb` | Parser version, source URL, timestamps. |
| `metadata` | `jsonb` | Legacy metadata, remains nullable for existing automations. |

### `insider_transactions`
Transaction-level rows extracted from each filing.

| Column | Type | Notes |
| --- | --- | --- |
| `transaction_id` | `bigserial` | Primary key. |
| `accession_number` | `text` | Foreign-key reference to `edgar_filings` via accession. |
| `transaction_date` | `date` | Reported transaction date. |
| `transaction_code` | `text` | SEC transaction code (`P`, `S`, etc.). |
| `symbol` | `text` | Issuer symbol for quick slicing. |
| `insider_name` | `text` | Insider name lifted from the filing. |
| `reporter_cik` | `text` | Insider CIK if disclosed. |
| `shares` | `numeric(20,4)` | Quantity traded. |
| `price` | `numeric(20,4)` | Price per share. |
| `metadata` | `jsonb` | Retained legacy payload metadata. |

A new unique index enforces `(accession_number, transaction_date, transaction_code, symbol)` to keep
re-ingestion idempotent.

### `daily_features`
Wide-table layout for FINRA off-exchange metrics.

| Column | Type | Notes |
| --- | --- | --- |
| `feature_id` | `bigserial` | Primary key. |
| `symbol` | `text` | Equity ticker. |
| `trade_date` | `date` | Trading session the features describe. |
| `short_vol_share` | `numeric(20,4)` | Short volume ÷ total volume. |
| `short_exempt_share` | `numeric(20,4)` | Short exempt ÷ total volume. |
| `ats_share_of_total` | `numeric(20,4)` | ATS share of total weekly volume. |
| `provenance` | `jsonb` | Feature version, source URLs, computation time. |

Unique index `(symbol, trade_date)` supports upserts from the Prefect flow.

### `signal_fingerprints`
Persistent vector representations for downstream similarity and backtests.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key. |
| `signal_name` | `text` | Logical signal identifier. |
| `version` | `text` | Semantic version string (e.g., `v2`). |
| `asset_symbol` | `text` | Asset scope. |
| `window_start` | `date` | Inclusive window start. |
| `window_end` | `date` | Inclusive window end (renamed from `as_of`). |
| `fingerprint` | `vector(128)` | pgvector embedding. |
| `provenance` | `jsonb` | Embedder names, feature configuration, hashes. |
| `meta` | `jsonb` | Free-form metadata for downstream agents. |
| `stats`, `tags` | `jsonb`, `text[]` | Legacy columns retained for compatibility. |

Unique index `(signal_name, version, asset_symbol, window_start, window_end)` guarantees a single
fingerprint per logical window.

## Seed Data (`supabase/seed.sql`)

The single seed file installs deterministic demo content:

- One Form 4 filing (`0000123456-24-000001`) with the associated insider transaction and provenance hashes.
- A FINRA feature row for `ACME` on `2024-12-30` with version metadata.
- A pgvector fingerprint with `window_start=2024-12-23`, `window_end=2024-12-30`, and matching provenance.
- Existing demo entries for `feature_registry`, `backtest_results`, and `signal_embeddings` retained for smoke tests.

Run `supabase db reset --local` to apply migrations and load the seeds. After reset you can
validate the demo payloads with:

```sql
select accession_number, symbol, reporter from public.edgar_filings;
select symbol, trade_date, short_vol_share from public.daily_features;
select signal_name, asset_symbol, window_start, window_end from public.signal_fingerprints;
```

These queries should return the seeded rows, confirming schema alignment with the new flows.
