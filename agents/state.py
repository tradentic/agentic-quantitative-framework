"""Shared state definitions for LangGraph planners."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class QuantAgentState:
    """Container passed between LangGraph nodes.

    The planner progressively enriches this state as it proposes new
    features, evaluates strategy performance, and schedules maintenance
    actions for the vector memory.
    """

    objective: str
    feature_plan: Dict[str, str] = field(default_factory=dict)
    feature_history: List[Dict[str, float | str]] = field(default_factory=list)
    backtest_result: Dict[str, float] = field(default_factory=dict)
    vector_actions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_note(self, message: str) -> None:
        """Append a human-readable note to the trace."""

        self.notes.append(message)

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serialisable representation of the state."""

        return {
            "objective": self.objective,
            "feature_plan": dict(self.feature_plan),
            "feature_history": list(self.feature_history),
            "backtest_result": dict(self.backtest_result),
            "vector_actions": list(self.vector_actions),
            "notes": list(self.notes),
        }
