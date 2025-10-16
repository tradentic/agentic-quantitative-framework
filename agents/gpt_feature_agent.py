"""Compat wrapper around the LangGraph agent for legacy callers."""

from __future__ import annotations

from typing import Any

from agents.langgraph_chain import run_planner


def analyze_and_propose(
    feature_log: dict[str, Any],
    backtest_summary: dict[str, Any],
) -> dict[str, Any]:
    """Invoke the LangGraph chain to generate a new feature proposal."""

    planner_state = run_planner(
        {
            "request": "propose new feature",
            "payload": {
                "intent": "propose_new_feature",
                "name": feature_log.get("candidate_name"),
                "description": feature_log.get("hypothesis"),
                "metadata": {
                    "source": "analyze_and_propose",
                    "backtest_metrics": backtest_summary,
                },
                "code": feature_log.get("generated_code") or "# TODO: implement feature\n",
            },
        }
    )
    return {
        "state": planner_state.get("long_term_state", {}),
        "results": planner_state.get("history", []),
    }
