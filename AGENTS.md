# AGENTS.md

## Role of Agents in This Project

This project uses GPT-5-level agents to orchestrate autonomous learning and signal discovery across financial datasets. Agents operate in a closed-loop feedback architecture, leveraging Supabase and LangGraph to coordinate long-lived reasoning, memory, and retraining. Core components include:

* Self-supervised feature generation (TS2Vec, DeepLOB, etc.)
* Symbolic regression (PySR) and transformation analysis
* Regime-aware labeling and window segmentation
* Supabase pgvector for similarity search and historical context recall
* Supabase triggers for feedback-aware retraining
* LangGraph as the runtime for memory, tool calls, and planning

## Agent Responsibilities

### 1. Feature Planning Agent

* Analyze decay and drift of features in backtest logs
* Propose symbolic, topological, or embedding-based feature variants
* Write scripts to `features/` and register metadata in Supabase

### 2. Strategy Evaluation Agent

* Consume model diagnostics, Sharpe stats, and live signal accuracy
* Schedule retraining, checkpoint deprecated signals
* Maintain configuration files under `config/`

### 3. Vector Intelligence Agent

* Monitor drift in Supabase pgvector embeddings
* Trigger similarity re-indexing when retraining or regime change occurs
* Maintain signal cluster snapshots in `vector_db/`

## Agent Entry Points

* Agents must reference: `docs/architecture/quant_ai_strategy_design.md`
* Agents run inside `agents/langgraph_chain.py` (or modular subchains)
* All agent-generated outputs must:

  * Be stored with metadata (creator, timestamp, backtrace)
  * Avoid duplicating existing feature keys or models unless explicitly versioned

## Supabase Integration Notes

* Vector DB: use `signal_embeddings` table in pgvector (with cosine index)
* Triggering: use Supabase RPC or realtime events to detect new embeddings and run agents
* Storage: Supabase buckets can hold serialized features or model artifacts

## Use Case Plugability

This framework is **modular and use-case agnostic**. To plug in a new use case:

* Define the anchor event (e.g. 13F filing, sentiment event)
* Label windows pre- or post-event using `labeling.py`
* Add embedding or feature extraction logic in `features/`
* Store labeled vectors to Supabase using `vector_db/indexer.py`

Each use case should live under: `use_cases/<use_case_name>/`

## Vision + Reference Docs

* Architecture: `docs/architecture/quant_ai_strategy_design.md`
* Insider trading prototype: `use_cases/insider_trading/Agentic Quant Loop.md`
* Dev setup & Supabase CLI: `LOCAL_DEV_SETUP.md`
