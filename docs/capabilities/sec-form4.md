# SEC Form 4 Ingestion Capability

## Motivation
- Provide a deterministic, back-fillable pipeline for insider transaction data.
- Normalize Form 4 filings into structured tables for downstream quantitative research.
- Capture provenance of each filing and transaction for auditability and compliance.

## Inputs
- EDGAR daily index files fetched via [`daily_index_urls`](../../framework/sec_client.py).
- Primary Form 4 XML documents resolved via [`accession_to_primary_xml_url`](../../framework/sec_client.py).
- Environment variables:
  - `SEC_HTTP_USER_AGENT`, `SEC_USER_AGENT`: override HTTP User-Agent header.
  - `SEC_HTTP_TIMEOUT`, `SEC_HTTP_RETRIES`, `SEC_HTTP_BACKOFF`: tune HTTP behaviour.
  - `SEC_FORM4_BATCH_SIZE`: controls persistence batch size.
  - Supabase credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` or equivalents).

## Outputs
- `edgar_filings`: single row per Form 4 filing with accession metadata, reporter details, XML URL, `filing_date`, and SHA-256 hashes (`xml_sha256`, `payload_sha256`).
- `insider_transactions`: expanded transaction rows (date, code, shares, price, insider name/CIK) linked via accession number and symbol for idempotent upserts.
- Prefect flow run results summarizing inserted filings and transactions.

## Configuration & Rate Limiting
- Respect SEC fair-use guidelines; user agent defaults to `agentic-quantitative-framework/0.1`.
- Retry strategy: exponential backoff (`SEC_HTTP_BACKOFF`) across `SEC_HTTP_RETRIES` attempts.
- Batch persistence controlled by `SEC_FORM4_BATCH_SIZE` (default `50`).
- Flow executes deterministically per calendar date; repeated runs are idempotent via upserts.

## CLI Examples
- Ingest a single day: `python -m flows.ingest_sec_form4 --date 2024-12-31`.
- Ingest a range: `python -m flows.ingest_sec_form4 --date-from 2024-12-01 --date-to 2024-12-31`.

## Failure Modes & Retries
- Missing index or XML files: logged and skipped after retry exhaustion, preserving determinism.
- Supabase misconfiguration: flow falls back to dry-run mode (parses data but skips persistence).
- Network issues: handled by built-in retry/backoff; persistent failures raise `EdgarHTTPError`.

## Validation Checks
- Unit tests under `tests/sec/` assert index parsing, URL derivation, and XML extraction.
- Flow logs per-date counts to verify batch sizes and ingestion coverage.
- Supabase upsert conflicts resolved on `accession_number` keys to avoid duplicates.

## Provenance
- Each filing record stores the canonical XML URL plus `xml_sha256` and `payload_sha256` hashes so downstream agents can detect drift.
- Transactions inherit accession numbers and share the filing's provenance hash, allowing merged auditing with `provenance_events`.
- Prefect task/flow logs maintain execution metadata for reproducibility.
