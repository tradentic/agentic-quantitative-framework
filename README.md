# Agentic Quantitative Framework

A modular, agent-driven framework for discovering and learning predictive financial signals using self-supervised learning, symbolic modeling, and vector-based signal memory.

## Key Features
- Self-supervised encoders (TS2Vec, DeepLOB)
- Symbolic regression and neural distillation
- GPT-agentic feedback loops (LangGraph / AutoGen)
- Vector database for signal memory and similarity
- Pluggable use cases (insider trading, regime shifts, etc.)
- Supabase-native local stack

## Repo Structure
- `agents/`: GPT-driven strategic planners
- `features/`: Feature generators, encoders, and pipelines
- `vector_db/`: Embedding logic and Supabase vector integration
- `backtest/`: Model evaluation and signal replay
- `use_cases/`: Concrete instantiations (e.g., insider_trading)
- `config/`: Model + pipeline config files
- `scripts/`: Ingestion jobs, retrain schedulers

## Setup
See `LOCAL_DEV_SETUP.md` for full Supabase CLI-based development guide.

## Authoring Agents
See `AGENTS.md` for how feature and strategy agents interact with system components.
