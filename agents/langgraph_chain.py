"""Durable LangGraph planner with Supabase-backed tools."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterable
from typing import Any, TypedDict, cast
from uuid import uuid4

from framework.supabase_client import (
    MissingSupabaseConfiguration,
    fetch_agent_state,
    persist_agent_state,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.tools import (
    propose_new_feature,
    prune_vectors,
    refresh_vector_store,
    run_backtest,
)

logger = logging.getLogger(__name__)


class PlannerState(TypedDict, total=False):
    """Typed representation of the LangGraph state payload."""

    request: str
    payload: dict[str, Any]
    messages: list[BaseMessage]
    guardrail_paths: list[str]
    history: list[dict[str, Any]]
    metrics: dict[str, Any]
    long_term_state: dict[str, Any]
    long_term_dirty: bool
    agent_id: str
    last_tool_name: str
    last_tool_result: dict[str, Any]
    completed: bool


class _SimpleTool:
    """Minimal tool adapter so ToolNode can invoke repository helpers."""

    def __init__(self, name: str, description: str, func: Any) -> None:
        self.name = name
        self.description = description
        self._func = func

    def invoke(self, input_dict: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = input_dict if isinstance(input_dict, dict) else {"input": input_dict}
        result = self._func(payload)
        if not isinstance(result, dict):
            raise TypeError(f"Tool '{self.name}' must return a dictionary payload.")
        return result

    async def ainvoke(
        self, input_dict: Any, config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.invoke(input_dict, config=config)


_TOOL_REGISTRY: dict[str, _SimpleTool] = {
    "propose_new_feature": _SimpleTool(
        "propose_new_feature",
        "Write or update feature modules and track metadata in Supabase.",
        propose_new_feature,
    ),
    "run_backtest": _SimpleTool(
        "run_backtest",
        "Execute backtests, persist artifacts, and register Supabase results.",
        run_backtest,
    ),
    "prune_vectors": _SimpleTool(
        "prune_vectors",
        "Archive or delete embeddings via rpc_prune_vectors.",
        prune_vectors,
    ),
    "refresh_vector_store": _SimpleTool(
        "refresh_vector_store",
        "Recompute embeddings and upsert them into signal_embeddings.",
        refresh_vector_store,
    ),
}


def _detect_intent(message: str | None) -> str:
    if not message:
        return "prune_vectors"
    lowered = message.lower()
    if any(keyword in lowered for keyword in ("feature", "ts2vec", "encoder")):
        return "propose_new_feature"
    if "backtest" in lowered or "sharpe" in lowered:
        return "run_backtest"
    if "prune" in lowered or "archive" in lowered:
        return "prune_vectors"
    if "refresh" in lowered or "embedding" in lowered:
        return "refresh_vector_store"
    return "prune_vectors"


def _hydrate_state(state: PlannerState) -> None:
    if state.get("long_term_state") is not None:
        return
    agent_id = state.get("agent_id")
    if not agent_id:
        state["long_term_state"] = {}
        return
    try:
        state["long_term_state"] = fetch_agent_state(agent_id)
    except MissingSupabaseConfiguration:
        logger.debug("Supabase configuration missing; continuing without hydration.")
        state["long_term_state"] = {}
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to hydrate agent state: %s", exc, exc_info=True)
        state["long_term_state"] = {}


def _ingest(state: PlannerState) -> PlannerState:
    messages = state.get("messages") or []
    state["messages"] = messages
    if "history" not in state:
        state["history"] = []
    if "metrics" not in state:
        state["metrics"] = {}
    _hydrate_state(state)
    request = state.get("request")
    if request:
        messages.append(HumanMessage(content=request))
    elif messages:
        # Already contains context
        pass
    else:
        messages.append(HumanMessage(content="Maintain embeddings."))
    return state


def _plan_next(state: PlannerState) -> PlannerState:
    messages = state["messages"]
    latest_request: str | None = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            if isinstance(msg.content, str):
                latest_request = msg.content
            elif isinstance(msg.content, list):
                latest_request = " ".join(str(part) for part in msg.content)
            break
    payload = state.get("payload") or {}
    intent = payload.get("intent") or _detect_intent(latest_request)
    if intent not in _TOOL_REGISTRY:
        raise ValueError(f"Unsupported tool intent: {intent}")
    tool_call_id = f"call_{uuid4().hex}"
    ai_message = AIMessage(
        content=f"Dispatching tool `{intent}` with payload keys: {sorted(payload.keys())}",
        tool_calls=[{"name": intent, "args": payload, "id": tool_call_id}],
    )
    messages.append(ai_message)
    state["last_tool_name"] = intent
    return state


def _parse_tool_message(message: ToolMessage) -> dict[str, Any]:
    content = message.content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}
        if isinstance(parsed, dict):
            return parsed
        return {"raw": parsed}
    if isinstance(content, list):
        return {"raw": content}
    if isinstance(content, dict):
        return content
    return {"raw": content}


def _collect_guardrail_paths(result: dict[str, Any], extras: Iterable[str]) -> list[str]:
    paths: set[str] = set()
    for key in ("file_path",):
        value = result.get(key)
        if isinstance(value, str) and value.endswith(".py"):
            paths.add(value)
    for key in ("created_files", "modified_files"):
        value = result.get(key)
        if isinstance(value, str) and value.endswith(".py"):
            paths.add(value)
        elif isinstance(value, Iterable):
            for item in value:
                if isinstance(item, str) and item.endswith(".py"):
                    paths.add(item)
    for extra in extras:
        if extra.endswith(".py"):
            paths.add(extra)
    return sorted(paths)


def _run_static_checks(paths: Iterable[str]) -> None:
    path_list = list(paths)
    if not path_list:
        return
    for command in ("ruff", "mypy"):
        try:
            subprocess.run([command, *path_list], check=True, text=True, capture_output=True)
        except FileNotFoundError:
            logger.warning("%s not available; skipping guardrail check.", command)
        except subprocess.CalledProcessError as exc:
            logger.error("%s failed: %s", command, exc.stderr)
            raise RuntimeError(f"Guardrail validation failed during {command}.") from exc


def _guardrails(state: PlannerState) -> PlannerState:
    messages = state["messages"]
    tool_message = next((m for m in reversed(messages) if isinstance(m, ToolMessage)), None)
    if not tool_message:
        return state
    payload = _parse_tool_message(tool_message)
    state["last_tool_result"] = payload
    guardrail_paths = _collect_guardrail_paths(payload, state.get("guardrail_paths") or [])
    _run_static_checks(guardrail_paths)
    if guardrail_paths:
        state.setdefault("guardrail_paths", [])
        state["guardrail_paths"].extend(
            [path for path in guardrail_paths if path not in state["guardrail_paths"]]
        )
    return state


def _persist_long_term_state(state: PlannerState) -> None:
    agent_id = state.get("agent_id")
    if not agent_id or not state.get("long_term_dirty"):
        return
    try:
        persist_agent_state(agent_id, state.get("long_term_state", {}))
    except MissingSupabaseConfiguration:
        logger.debug("Supabase configuration missing; skipping state persistence.")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to persist agent state: %s", exc, exc_info=True)
    else:
        state["long_term_dirty"] = False


def _reflect(state: PlannerState) -> PlannerState:
    tool_name = state.get("last_tool_name")
    tool_result = state.get("last_tool_result") or {}
    if not tool_name:
        return state
    record = {
        "tool": tool_name,
        "result": tool_result.get("result", tool_result),
    }
    history = state.setdefault("history", [])
    history.append(record)
    metrics = state.setdefault("metrics", {})
    if isinstance(tool_result.get("result"), dict):
        metrics[tool_name] = tool_result["result"]
    long_term = state.setdefault("long_term_state", {})
    long_term.setdefault("history", [])
    long_term["history"] = (long_term["history"] + [record])[-15:]
    if metrics:
        long_term["metrics"] = metrics
    state["long_term_dirty"] = True
    _persist_long_term_state(state)
    state["completed"] = True
    return state


def _should_continue(state: PlannerState) -> str:
    if state.get("completed"):
        return "END"
    return "plan"


def build_planner(*, checkpointer: MemorySaver | None = None):
    """Compile the LangGraph planner with a configurable checkpointer."""

    workflow = StateGraph(PlannerState)
    tool_node = ToolNode(cast(list[Any], list(_TOOL_REGISTRY.values())))
    workflow.add_node("ingest", _ingest)
    workflow.add_node("plan", _plan_next)
    workflow.add_node("tools", tool_node)
    workflow.add_node("guard", _guardrails)
    workflow.add_node("reflect", _reflect)

    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "plan")
    workflow.add_conditional_edges("plan", tools_condition, {"tools": "tools", "END": END})
    workflow.add_edge("tools", "guard")
    workflow.add_edge("guard", "reflect")
    workflow.add_conditional_edges("reflect", _should_continue, {"plan": "plan", "END": END})

    return workflow.compile(checkpointer=checkpointer or MemorySaver())


def run_planner(
    state: dict[str, Any], *, thread_id: str = "local", checkpointer: MemorySaver | None = None
) -> dict[str, Any]:
    """Convenience helper for invoking the planner in scripts or smoke tests."""

    graph = build_planner(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    return cast(dict[str, Any], graph.invoke(state, config=config))


__all__ = ["PlannerState", "build_planner", "run_planner"]


# Smoke test
# >>> if __name__ == "__main__":
# ...     result = run_planner(
# ...         {"request": "refresh embeddings", "payload": {"asset_symbol": "AAPL", "windows": []}}
# ...     )
# ...     print(result.get("last_tool_name"))
