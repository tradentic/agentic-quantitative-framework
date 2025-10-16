"""Base abstractions for use case orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agents.langgraph_chain import run_planner


@dataclass
class UseCaseRequest:
    """Canonical payload that is fed into the LangGraph agent."""

    intent: str
    payload: dict[str, Any]
    model: str | None = None
    messages: list[Any] = field(default_factory=list)


@dataclass
class StrategyUseCase:
    """Base class for defining reusable agent use cases."""

    name: str
    description: str

    def build_request(self, **kwargs: Any) -> UseCaseRequest:
        raise NotImplementedError

    def dispatch(self, **kwargs: Any) -> dict[str, Any]:
        request = self.build_request(**kwargs)
        payload = {
            "intent": request.intent,
            **request.payload,
            "requested_at": datetime.utcnow().isoformat(),
        }
        if request.model:
            payload["model"] = request.model
        initial_state: dict[str, Any] = {
            "request": request.intent,
            "payload": payload,
            "messages": request.messages,
        }
        return run_planner(initial_state)
