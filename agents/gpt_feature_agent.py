"""Compat wrapper around the LangGraph agent for legacy callers."""

from __future__ import annotations

from typing import Any

from agents.langgraph_chain import AgentState, build_langgraph_chain


def analyze_and_propose(
    feature_log: dict[str, Any],
    backtest_summary: dict[str, Any],
) -> dict[str, Any]:
    """Invoke the LangGraph chain to generate a new feature proposal."""

    chain = build_langgraph_chain()
    state = AgentState(
        task_context={
            "intent": "propose_new_feature",
            "payload": {
                "name": feature_log.get("candidate_name"),
                "description": feature_log.get("hypothesis"),
                "metadata": {
                    "source": "analyze_and_propose",
                    "backtest_metrics": backtest_summary,
                },
            },
        },
    )
    result_state = chain.invoke(state)
    return {
        "state": result_state.task_context,
        "results": result_state.results,
    }
