"""Compat wrapper around the LangGraph agent for legacy callers."""

from __future__ import annotations

from typing import Any

from agents.langgraph_chain import run_planner


def analyze_and_propose(
    feature_log: dict[str, Any],
    backtest_summary: dict[str, Any],
) -> dict[str, Any]:
    """Invoke the LangGraph chain to generate a new feature proposal."""

    result_state = run_planner(
        {
            "context": {
                "agent_id": "feature-agent",
                "intent": "propose_new_feature",
                "payload": {
                    "name": feature_log.get("candidate_name"),
                    "description": feature_log.get("hypothesis"),
                    "metadata": {
                        "source": "analyze_and_propose",
                        "backtest_metrics": backtest_summary,
                    },
                },
            }
        }
    )
    return {
        "state": result_state.get("context", {}),
        "results": result_state.get("results", []),
    }
