# ADR 2025-10-17: Establish `provenance_events` lineage table

## Status
Accepted

## Context
Audit 2025-10-16 flagged that `framework.provenance.record_provenance` writes to a `provenance_events` table that was never created in Supabase. Without a dedicated lineage table, agents recording hashes, parser versions, and fetch timestamps silently fail, breaking downstream traceability commitments documented in `docs/capabilities/provenance.md` and compliance workflows such as insider trading reviews.

## Decision
- Create migration `20251017_create_provenance_events.sql` establishing `public.provenance_events` with a `bigserial` primary key, JSONB payload column, optional provenance metadata (source URL, parser version, artifact hash), and a defaulted `created_at` timestamp. The table comment captures its role as the audit log for provenance hashes and fetch context.
- Add a Supabase seed (`20251017_provenance_seed.sql`) inserting a representative Form 4 lineage record so schema diffs and smoke tests can validate JSON access patterns end-to-end.
- Extend automated tests with `tests/db/test_provenance_table.py`, using an in-memory transactional Supabase client to verify that `record_provenance` inserts payloads and preserves JSON metadata needed for forensic lookups.

## Consequences
- Provenance writes from ingestion and feature flows now land in a durable table, unblocking analytics that join operational data to lineage metadata.
- Seeds and tests guard against regressions where the table or JSON structure drifts from the expectations encoded in `framework.provenance.PROVENANCE_TABLE`.
- Supabase deployments gain an additional trigger function to maintain `updated_at`, aligning provenance events with other timestamped tables.

## Rollback Plan
1. Revert migration `20251017_create_provenance_events.sql` to drop the table, trigger, and helper function if the lineage layer needs to be disabled.
2. Remove the provenance seed file from deployment manifests to avoid inserting stale demo rows.
3. Delete or xfail `tests/db/test_provenance_table.py` to prevent CI from failing once the table is removed.
4. Communicate to downstream teams that provenance joins will no longer resolve and update documentation pointing at the lineage catalog.
