"""LangGraph planner wiring for the Agentic Quantitative Framework."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from langgraph.graph import CompiledGraph, END, StateGraph

from .state import QuantAgentState
from .tools import (
    propose_new_feature,
    prune_vectors,
    refresh_vector_store,
    run_backtest,
)


def _plan_features(state: QuantAgentState) -> QuantAgentState:
    """Plan the next feature experiment based on historical performance."""

    proposed = propose_new_feature(state.feature_history, state.objective)
    state.feature_plan = proposed
    state.add_note(
        "Planned feature '{name}' with transform `{transform}`.".format(
            name=proposed.get("name", "unknown"),
            transform=proposed.get("transform", "n/a"),
        )
    )
    return state


def _evaluate_strategy(state: QuantAgentState) -> QuantAgentState:
    """Run a deterministic backtest to score the current feature plan."""

    metrics = run_backtest(state.feature_plan)
    state.backtest_result = metrics
    state.feature_history.append(
        {
            "name": state.feature_plan.get("name", "unknown"),
            "sharpe": metrics.get("sharpe", 0.0),
            "calmar": metrics.get("calmar", 0.0),
        }
    )
    state.add_note(
        "Backtest metrics recorded: "
        f"Sharpe={metrics.get('sharpe')}, Calmar={metrics.get('calmar')}"
    )
    return state


def _maintain_vector_memory(state: QuantAgentState) -> QuantAgentState:
    """Decide how to maintain the vector memory based on drift signals."""

    last_refresh = datetime.now(tz=UTC) - timedelta(days=7)
    drift_score = 0.42 if state.backtest_result.get("sharpe", 0.0) > 0.8 else 0.25
    prune_message = prune_vectors(last_refresh, drift_score)
    refresh_message = refresh_vector_store(
        reason="post-backtest alignment", target_collections=["features", "signals"]
    )

    state.vector_actions = [prune_message, refresh_message]
    state.add_note(prune_message)
    state.add_note(refresh_message)
    return state


class QuantitativePlanner:
    """Thin wrapper around a compiled LangGraph state machine."""

    def __init__(self) -> None:
        self.graph = build_quant_signal_graph()

    def invoke(self, objective: str) -> QuantAgentState:
        """Execute the planner end-to-end for the supplied objective."""

        state = QuantAgentState(objective=objective)
        result_state: Any = self.graph.invoke(state)
        if isinstance(result_state, QuantAgentState):
            return result_state
        if isinstance(result_state, dict):
            return QuantAgentState(**result_state)
        raise TypeError("Unsupported state returned from LangGraph execution")


def build_quant_signal_graph() -> CompiledGraph:
    """Construct and return the LangGraph planner."""

    graph: StateGraph[QuantAgentState] = StateGraph(QuantAgentState)
    graph.add_node("plan_features", _plan_features)
    graph.add_node("evaluate_strategy", _evaluate_strategy)
    graph.add_node("maintain_vector_memory", _maintain_vector_memory)

    graph.set_entry_point("plan_features")
    graph.add_edge("plan_features", "evaluate_strategy")
    graph.add_edge("evaluate_strategy", "maintain_vector_memory")
    graph.add_edge("maintain_vector_memory", END)

    return graph.compile()


__all__ = ["QuantitativePlanner", "build_quant_signal_graph"]
