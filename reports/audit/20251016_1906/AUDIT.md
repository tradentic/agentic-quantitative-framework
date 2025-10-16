**Repo**: agentic-quantitative-framework
**Branch/SHA**: work @ 9156502

### Summary
Post-merge review confirms the expected quant feature stack is largely in place (features, flows, agents, Supabase schema), but several production gaps remain: MiniRocket embeddings fail under NumPy 2.0, TS2Vec and DeepLOB rely on optional dependencies without guardrails, matrix-profile runs stall under Numba compilation, and vector upserts are not idempotent because every insert generates a fresh UUID. Microstructure/VPIN utilities enforce strict column contracts and Prefect orchestration is defined, yet `prefect deployments ls` cannot be validated due to the ephemeral server crash. Configuration templates and provenance hooks exist, so the main follow-up work is dependency hardening, runtime fallbacks, and deterministic persistence. 【f4c8b9†L1-L4】【df0c09†L71-L79】【F:features/generate_ts2vec_embeddings.py†L40-L94】【F:features/deeplob_embeddings.py†L35-L199】【114788†L1-L73】【F:framework/supabase_client.py†L109-L184】【93567f†L1-L54】【F:.env.example†L1-L20】【F:framework/provenance.py†L13-L77】

### Architecture Parity
| Intended Component | Observed Implementation | Notes |
| --- | --- | --- |
| Feature extractors | `features/` with change-point, matrix profile, Hawkes, TS2Vec, DeepLOB, MiniRocket, microstructure, VPIN modules.【F:features/change_points.py†L1-L120】【F:features/matrix_profile.py†L31-L89】【F:features/hawkes_features.py†L1-L200】【F:features/generate_ts2vec_embeddings.py†L40-L94】【F:features/deeplob_embeddings.py†L35-L199】【F:features/minirocket_embeddings.py†L1-L83】【F:features/microstructure.py†L1-L200】【F:features/vpin.py†L1-L197】 | MiniRocket currently raises on import under NumPy 2.0.【df0c09†L71-L79】 |
| Framework clients | `framework/` housing Supabase, SEC, FINRA, provenance utilities.【F:framework/supabase_client.py†L1-L200】【F:framework/provenance.py†L1-L77】 | Supabase client enforces retries but needs deterministic upsert keys.【F:framework/supabase_client.py†L109-L184】 |
| Prefect flows | `prefect.yaml` plus flow modules for ingestion, embeddings, similarity, backtests.【F:prefect.yaml†L1-L104】【F:flows/similarity_scans.py†L259-L334】【F:flows/backtest.py†L1-L120】 | CLI deployment listing fails due to temp server crash.【93567f†L1-L54】 |
| Agents & tools | `agents/` LangGraph orchestrator + Supabase-backed tool registry.【F:agents/langgraph_chain.py†L1-L200】【F:agents/tools.py†L20-L118】 | Tools persist features/backtests/artifacts to Supabase.【F:agents/tools.py†L56-L116】 |
| Supabase schema | `supabase/migrations/` with vector tables, insider objects, RPCs, seeds.【F:supabase/migrations/20240101001000_baseline_schema.sql†L4-L83】【F:supabase/migrations/20250101000000_core_schema.sql†L6-L98】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L5-L88】 | `signal_embeddings` lacks unique constraint for idempotent writes.【F:supabase/migrations/20240101001000_baseline_schema.sql†L4-L20】 |
| Insider use-case | `use_cases/insider_trading/` pipeline + config.【F:use_cases/insider_trading/pipeline.py†L1-L200】 | Depends on Supabase client and provenance constants.【F:use_cases/insider_trading/pipeline.py†L15-L17】 |

### Capability Matrix
See `CAPABILITY_MATRIX.md` for the full grid; highlights include ✅ vector store & microstructure/VPIN, ⚠️ TS2Vec/DeepLOB/matrix profile/idempotency, ❌ MiniRocket due to NumPy 2.0 breakage.【F:reports/audit/20251016_1906/CAPABILITY_MATRIX.md†L1-L15】

### Evidence
1. **Features** – PELT/BOCPD change-point detection succeeds on synthetic data, but microstructure/VPIN smoke tests fail without timestamp/size columns and matrix-profile compilation stalls under stumpy/numba.【eb83af†L1-L18】【114788†L1-L73】 MiniRocket import raises AttributeError because NumPy removed `np.float_`.【df0c09†L71-L79】 Hawkes utilities provide exponential fit diagnostics.【F:features/hawkes_features.py†L1-L200】
2. **Agents/Tools** – LangGraph chain wires Supabase-backed tools for feature proposals, backtests, vector pruning, and embedding refresh; each tool persists artefacts or registry records via Supabase helper methods.【F:agents/langgraph_chain.py†L20-L188】【F:agents/tools.py†L20-L118】
3. **Flows** – Prefect deployments declared for embedding refresh, backtests, pruning, SEC ingestion, similarity scans, etc., and AST scan confirms flow entrypoints; however, CLI listing crashed because temporary server reset the connection.【F:prefect.yaml†L3-L104】【70f9fb†L1-L21】【93567f†L1-L54】
4. **Database** – Migrations enable pgvector/uuid, define embedding, fingerprint, filings, transactions, daily features, and text chunk tables with relevant indexes; fingerprints enforce uniqueness but embeddings rely solely on UUID primary key.【F:supabase/migrations/20240101000000_setup_pgvector.sql†L1-L4】【F:supabase/migrations/20240101001000_baseline_schema.sql†L4-L83】【F:supabase/migrations/20250101000000_core_schema.sql†L6-L98】【F:supabase/migrations/20250301090000_align_insider_pipeline_schema.sql†L25-L70】【F:supabase/migrations/20240901090000_align_langgraph_supabase_schema.sql†L6-L35】
5. **Config** – `.env.example` enumerates Supabase, LLM, and Prefect environment variables but omits optional vendor keys (Polygon/FINRA) used elsewhere.【F:.env.example†L1-L20】
6. **Provenance/Idempotency** – Provenance helper hashes payloads and upserts into configurable table; embedding insertions generate random UUIDs, so repeat runs create duplicate rows unless upstream de-duplicates.【F:framework/provenance.py†L13-L77】【F:framework/supabase_client.py†L109-L184】

### Patch Plan (Condensed)
Refer to `PATCH_PLAN.md` for proposed follow-up branches covering MiniRocket NumPy fixes, deterministic embedding upserts, matrix profile runtime guards, documentation of microstructure inputs, and DeepLOB asset packaging.【F:reports/audit/20251016_1906/PATCH_PLAN.md†L1-L37】

### Questions Needed
Open items (credentials, dependency strategy, Prefect target, sample datasets, GPU availability) are tracked in `QUESTIONS.md`.【F:reports/audit/20251016_1906/QUESTIONS.md†L1-L13】
