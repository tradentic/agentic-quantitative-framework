# Changelog

## 2025-03-01

- Added additive Supabase migration aligning `edgar_filings`, `insider_transactions`, `daily_features`, and `signal_fingerprints` with the insider pipeline and refreshed demo seeds.
- Extended Form 4, FINRA, and fingerprint Prefect flows to emit schema-compatible payloads with provenance hashes and pgvector guardrails.
- Deferred MiniRocket optional dependency imports, expanded unit coverage, and wired the insider trading pipeline to orchestrate ingestion, features, fingerprints, similarity scans, and backtests.

## 2025-10-16

- Adopted Prefect-based orchestration flows for embeddings, backtests, and pruning defined in `prefect.yaml`.
- Enhanced `agents/langgraph_chain.py` with Supabase-backed memory, tool metrics, and static-analysis guardrails.
- Added typed Supabase helpers, pgvector schema migrations, and documentation updates covering Prefect workflows.
