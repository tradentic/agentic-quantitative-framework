# Insider Trading Signal Loop

This playbook documents how the Agentic Quantitative Framework is configured
for insider trading anomaly detection.

- **Anchor events:** Form 4 filings with trade size above threshold
- **Labelling:** Positive labels for statistically abnormal alpha over 10-day horizon
- **Feature pack:** Short interest shocks, liquidity vacuum detectors, insider cluster embeddings
- **Backtest cadence:** Nightly re-runs with 90-day rolling windows

Update this file as the loop evolves so LangGraph agents have auditable context
when switching between strategies.
