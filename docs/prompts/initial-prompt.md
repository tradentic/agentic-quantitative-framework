# Agent Task: Refactor Repository into Agentic Quantitative Framework Architecture

## GOAL
You are acting as a senior infrastructure and AI systems engineer. Refactor this repo to align tightly with the architecture defined in:

📄 `docs/architecture/quant_ai_strategy_design.md`

## CONTEXT
This repo includes:
- A LangGraph-based agentic loop for self-improving signal detection
- Supabase integration for vector DB, local database, and realtime triggers
- Additional inherited components (Docusaurus, .devcontainer/, .github workflows)

Your job is to normalize the repo structure, update naming, and ensure tight compliance with the Quant AI architecture.

## OBJECTIVES

### ✅ 1. ARCHITECTURE ALIGNMENT
- Ensure agentic workflow uses LangGraph in `agents/langgraph_chain.py`
- Clean up any incompatible or legacy files
- Relocate all use-case-specific logic to `use_cases/<use_case_name>/`

### 💾 2. SUPABASE-FIRST POLICY
Where applicable, always **prefer Supabase-native solutions over external dependencies**, including:
- Vector DB → use Supabase pgvector (not Pinecone/Faiss unless fallback is needed)
- Storage → use Supabase buckets for feature exports or model artifacts
- Realtime → use Supabase triggers for auto-refresh, retrain, or embed

Do not install redundant tooling if Supabase provides the same feature set.

### 📘 3. DOCUSAURUS + NAMING CLEANUP
- Update docs site config (title, nav bar) to reflect this as the “Agentic Quantitative Framework”
- Remove or rename any doc pages or folders that refer to old project names
- Ensure core architecture doc remains at: `docs/architecture/quant_ai_strategy_design.md`
- Add placeholder pages if missing:
  - `/docs/agents.md`
  - `/docs/backtesting.md`
  - `/docs/deployment.md`

### 🐳 4. DEVCONTAINER SUPPORT
Ensure `.devcontainer/devcontainer.json`:
- Installs Python 3.11+
- Installs `supabase` CLI
- Installs Node.js 18+ for Docusaurus
- Installs any Supabase extensions (pgvector, realtime triggers)
- Opens ports 54321, 54322, 3000

### 🧪 5. WORKFLOWS
- Rename GitHub workflows clearly:
  - `ci.yml` → test, lint, typecheck
  - `docs.yml` → Docusaurus build/test
- Confirm these reference updated repo name and structure

---

## ✅ ARCHITECTURE DECISION RECORDS (ADR)

For all key infrastructure decisions, write ADR files into:

📁 `docs/architecture/adr/`

Start with these two:

### `0001-use-supabase-for-local-stack.md`
> We choose Supabase for the local development stack due to its integrated Postgres (with pgvector), S3-compatible storage, and built-in Realtime features. It is Dockerized, developer-friendly, and serves as a unified backend for this AI agentic system.

### `0002-use-supabase-as-vector-db.md`
> Instead of Pinecone or Faiss, we use Supabase with `pgvector` for embedding storage. It supports similarity search, native SQL, and unifies with the rest of the Supabase environment, improving maintainability and developer experience.

---

## CONSTRAINTS
- Do not break existing Docusaurus or Supabase configurations
- Do not introduce additional cloud dependencies unless absolutely necessary
- Favor Pythonic, reproducible workflows (e.g., minimal bash scripts, clear Makefile if used)

## FINAL OUTPUT
A refactored, Supabase-native, LangGraph-ready repo structure that:
- Implements the quant_ai_strategy_design.md architecture
- Follows modern AI infra standards
- Is fully documented with ADRs and developer guidance
