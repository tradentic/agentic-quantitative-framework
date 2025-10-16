# AGENTS.md

## Role of Agents in This Project

This project uses GPT-5-level agents to serve as strategic planners, feature engineers, and continuous learners in a closed feedback loop. The system integrates:

- Self-supervised feature generation (TS2Vec, DeepLOB, etc.)
- Symbolic regression (PySR)
- Regime-aware labeling and validation
- Similarity search using vector databases (FAISS, Pinecone)
- Continual learning based on performance feedback

## Agent Responsibilities

### 1. Feature Planning Agent
- Analyze signal decay, drift, and backtest outcomes
- Propose new features or transforms (e.g., bid-ask imbalance + dark pool share)
- Write feature generator scripts to `features/`

### 2. Strategy Evaluation Agent
- Read backtest logs and Sharpe metrics
- Suggest retraining schedules or model refresh
- Write configs to `config/model/` manifests and `config/schedules/`

### 3. Vector Intelligence Agent
- Monitor embedding quality and drift
- Re-index vector DB if model or data changes
- Trigger similarity search and cluster analysis in `vector_db/`

## Agent Entry Points

- Agents should reference `Quant Ai Strategy Design.md` for the full system vision
- Agents may operate via LangGraph, AutoGen, or compatible tool interfaces
- All agent-generated artifacts should include trace metadata and be saved in versioned locations

## Use Case Plugability

This framework supports arbitrary use cases by defining:
- A new anchor event (e.g. earnings, filings, sentiment spikes)
- A custom labeling regime
- A tailored set of features or data sources

Use cases should be placed under `use_cases/<use_case_name>/` with a manifest or setup file.

## Vision + Architecture Docs

- System vision: `Quant Ai Strategy Design.md`
- Example instantiation: `use_cases/insider_trading/Agentic Quant Loop.md`
