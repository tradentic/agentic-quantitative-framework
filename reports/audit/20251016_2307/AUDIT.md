**Repo**: agentic-quantitative-framework
**Branch/SHA**: work @ 85552ab

### Summary
Post-merge inspection shows the quantitative feature stack is largely intact: matrix profile, change-point, Hawkes, microstructure, and VPIN modules all load and pass synthetic smoke tests, and Supabase migrations cover core tables plus pgvector triggers. However, advanced embedding workflows remain gated behind optional dependencies (TS2Vec, MiniRocket, DeepLOB) and missing artifacts, the Prefect deployments defined in `prefect.yaml` have not been registered, and there is no `provenance_events` table to receive provenance writes. Insider use-case glue and Supabase clients are wired, yet they depend on secrets, FINRA/Polygon access, and PCA assets that are absent from the runtime, leaving the overall capability in a partially operational state.

### Architecture Parity
| Intended Component | Actual Location(s) | Notes |
| --- | --- | --- |
| Feature extractors (matrix profile, change-points, Hawkes, microstructure, VPIN, embeddings) | `features/` | Modules exist; TS2Vec falls back to identity, MiniRocket/DeepLOB blocked by missing deps. |
| Framework clients (Supabase, SEC, FINRA, vendor markets, provenance) | `framework/` | Supabase client implements retries/pgvector helpers; provenance writer lacks backing table. |
| Prefect flows (ingest, features, embeddings, scans, backtest) | `flows/`, `prefect.yaml` | Nine flows discovered; deployments declared but not registered in Prefect server. |
| Agents & tools | `agents/` | LangGraph planner exposes feature/backtest/vector tools; depends on Supabase state persistence. |
| Supabase migrations & seeds | `supabase/` | Extensive migration chain, but missing provenance table; idempotency/enforcement migrations rely on sequential renames. |
| Use case glue (insider trading) | `use_cases/insider_trading/` | Pipeline + YAML config orchestrate SEC ingest → features → embeddings → scans → backtest, contingent on external services and PCA artifacts. |

### Capability Matrix
| Capability | Status |
| --- | --- |
| Vector store / pgvector | ⚠️ Partial |
| TS embeddings | ⚠️ Partial |
| MiniRocket | ⚠️ Partial |
| DeepLOB | ⚠️ Partial |
| Microstructure | ✅ Present |
| VPIN | ✅ Present |
| Matrix Profile | ✅ Present |
| Change-points | ✅ Present |
| Hawkes | ✅ Present |
| Use-case glue | ⚠️ Partial |
| Backtests | ⚠️ Partial |
| Similarity scans | ⚠️ Partial |
| Provenance | ⚠️ Partial |
| Idempotency | ⚠️ Partial |

### Evidence
1. **Features** — see `FEATURE_INVENTORY.md` for module-by-module status. Smoke tests executed for matrix profile, change-points, Hawkes, microstructure, VPIN, and TS2Vec fallback. MiniRocket/DeepLOB currently fail due to missing optional packages.
2. **Agents/Tools** — `agents/tools.py` exposes Supabase-integrated feature proposal, backtests, vector refresh, and pruning. `agents/langgraph_chain.py` builds a LangGraph planner with guardrail hooks but depends on Supabase state fetch/persist and optional LangChain support.
3. **Flows** — `prefect.yaml` enumerates nine deployments; `FLOWS_CHECK.md` lists discovered `@flow` entrypoints. Prefect CLI (v3.4.24) reports no registered deployments.
4. **Database** — `SCHEMA_CHECK.md` summarises migrations: pgvector extensions, signal embeddings/fingerprints tables, daily feature alignment, idempotency constraints, and seeds. Notably absent is the `provenance_events` table referenced by `framework/provenance.py`.
5. **Config** — `.env.example` includes Supabase, Prefect, and LLM keys but omits optional embedding dependencies. Vendor clients (Polygon) rely on `POLYGON_API_KEY`; FINRA endpoints configurable via `FINRA_BASE_URL`.
6. **Provenance & Idempotency** — `framework/provenance` hashes records and writes to Supabase; without the table migration, writes will fail silently. `supabase/migrations/20251016_idempotency.sql` enforces unique keys on `daily_features`/`signal_fingerprints`, assuming alignment migration has run.

### Patch Plan (Condensed)
- Add a Supabase migration creating `provenance_events`, seed data, and ensure idempotent indexes survive renames.
- Publish optional embedding dependencies and tests so TS2Vec/MiniRocket/DeepLOB pathways are usable or gracefully skipped.
- Provide Prefect deployment automation plus example similarity queries to validate the orchestration layer without manual setup.
- Harden insider pipeline defaults (mocking, PCA artifact management) and document required secrets per module.

### Questions Needed
See `QUESTIONS.md` for the credentials, dependency decisions, and sample payloads required to complete integration testing.
