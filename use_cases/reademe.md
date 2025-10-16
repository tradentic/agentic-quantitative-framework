# Use Cases

This section contains concrete implementations of agent-driven quantitative strategies and signal workflows. Each use case plugs into the modular architecture defined in the [Quant AI Strategy Design](../architecture/quant_ai_strategy_design.md) and demonstrates how autonomous agents, self-supervised features, and vector-based learning loops can be applied to specific financial objectives.

Use cases follow a consistent structure:
- Defined anchor events (e.g., insider filings, regime shifts)
- Custom labeling and feature generation logic
- Integration into the agentic loop via LangGraph and Supabase
- Performance evaluation and vector signal tracking

---

## 📌 Available Use Cases

### [Insider Trading Anomaly Detection](insider_trading/Agentic%20Quant%20Loop.md)
> A GPT-guided strategy that detects market behavior patterns indicative of insider trades — before the SEC filings are released. Combines Form 4 parsing, deep feature encodings, and vector DB recall.

---

## 🔌 Adding a New Use Case

To add a new strategy module:
1. Create a folder: `/use_cases/<your_strategy>/`
2. Add:
   - An architecture overview `.md`
   - Sample data ingestion logic (optional)
   - Labeling and feature definitions
3. Register embeddings to the vector DB
4. Connect to the agent pipeline in `agents/langgraph_chain.py`

