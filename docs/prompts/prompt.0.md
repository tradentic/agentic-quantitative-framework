# Agent Task: Refactor Repository to Match the Agentic Quantitative Framework

## GOAL
You are an autonomous coding agent responsible for aligning this repo to a GPT-driven signal discovery framework. The architecture is defined here:

📄 `docs/architecture/quant_ai_strategy_design.md`  
📄 `AGENTS.md` (updated agent roles and responsibilities)

## KEY CONSTRAINTS

✅ Use Supabase as the default stack  
✅ Do not rename or delete any `.github/` or `.devcontainer/` files  
✅ Do not overwrite `supabase/config.toml` — it has been manually configured  
✅ All Markdown docs must load cleanly in Docusaurus (valid frontmatter, no broken paths)

---

## OBJECTIVES

### 1. ARCHITECTURE COMPLIANCE
- Ensure the LangGraph agent chain is implemented in `agents/langgraph_chain.py`
- Supported tool functions: `propose_new_feature()`, `run_backtest()`, `prune_vectors()`, `refresh_vector_store()`
- Organize strategy-specific logic under `use_cases/<use_case_name>/`

### 2. SUPABASE-FIRST IMPLEMENTATION
- Use Supabase pgvector (`signal_embeddings` table) as the primary vector store
- Use Supabase buckets for storage (model artifacts, features)
- Use Supabase triggers or RPC to automate embedding workflows
- Do not install FAISS, Pinecone, or redundant vector DBs unless required for comparison

### 3. DOCUSAURUS DOC MANAGEMENT
- Validate all docs in `docs/` render correctly (especially under `/docs/architecture/`)
- Architecture reference must remain at: `docs/architecture/quant_ai_strategy_design.md`
- Add or fix these if missing:
  - `docs/agents.md`
  - `docs/backtesting.md`
  - `docs/deployment.md`

### 4. ADD ADRs FOR ARCHITECTURE CHOICES
Add these ADRs in: `docs/architecture/adr/`

#### `0001-use-supabase-for-local-stack.md`
> Supabase is chosen as the local stack due to its unified Postgres, vector DB, storage, and realtime capabilities — ideal for agent-driven AI research and reproducible dev environments.

#### `0002-use-supabase-as-vector-db.md`
> Supabase pgvector replaces external vector DBs like Pinecone or FAISS. It supports similarity search and integrates seamlessly with Supabase triggers, buckets, and observability.

### 5. CLEANUP AND CONSISTENCY
- Update `.env.example` to reflect Supabase and dev container setup
- Update `README.md` and docs nav to reflect current repo purpose
- Refactor CI/CD workflows in `.github/` if needed — but don’t delete
- Ensure `.devcontainer/` installs: Python 3.11, Supabase CLI, Node.js 24, Poetry or pip

---

## FINAL DELIVERABLE

A fully cleaned, consistent, LangGraph-native repo that:
- Uses Supabase as its backend and vector system
- Has valid documentation and working dev setup
- Enables autonomous agents to reason, learn, and self-improve
