"""Base abstractions for use case orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agents.langgraph_chain import AgentState, build_langgraph_chain


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

    def dispatch(self, **kwargs: Any) -> AgentState:
        request = self.build_request(**kwargs)
        chain = build_langgraph_chain()
        state = AgentState(
            task_context={
                "intent": request.intent,
                "payload": request.payload,
                "model": request.model,
                "requested_at": datetime.utcnow().isoformat(),
            },
            messages=request.messages,
        )
        return chain.invoke(state)
