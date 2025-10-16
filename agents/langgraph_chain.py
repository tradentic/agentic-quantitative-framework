"""LangGraph planner with Supabase-backed memory and tool execution."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterable, Sequence
from datetime import datetime
from importlib import import_module, util
from typing import Any, TypedDict, cast
from uuid import uuid4

from framework.supabase_client import (
    MissingSupabaseConfiguration,
    fetch_agent_state,
    persist_agent_state,
)
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from agents.tools import (
    propose_new_feature,
    prune_vectors,
    refresh_vector_store,
    run_backtest,
)

logger = logging.getLogger(__name__)

HISTORY_WINDOW = 5


class PlannerState(TypedDict, total=False):
    """Shared state dictionary that flows between LangGraph nodes."""

    context: dict[str, Any]
    task_context: dict[str, Any]
    messages: list[Any]
    history: list[dict[str, Any]]
    results: list[dict[str, Any]]
    metrics: dict[str, Any]
    pending_tool: str
    tool_invocation: dict[str, Any]
    validated_paths: list[str]
    guardrail_paths: list[str]
    long_term_state: dict[str, Any]
    long_term_dirty: bool
    completed: bool


class _DictPayload(BaseModel):
    """Wrapper schema used to expose dict-style payloads to LangGraph tools."""

    payload: dict[str, Any] = Field(default_factory=dict)


def _build_tool_router() -> ToolNode:
    """Create a LangGraph ToolNode that wraps Supabase-aware callables."""

    def _wrap(func: Any, name: str, description: str) -> StructuredTool:
        def _runner(payload: dict[str, Any]) -> dict[str, Any]:
            return cast(dict[str, Any], func(payload))

        return StructuredTool.from_function(
            _runner,
            name=name,
            description=description,
            args_schema=_DictPayload,
        )

    tools = [
        _wrap(
            propose_new_feature,
            "propose_new_feature",
            "Create or update feature modules and register metadata in Supabase.",
        ),
        _wrap(
            run_backtest,
            "run_backtest",
            "Execute the local backtest engine and persist metrics/artifacts.",
        ),
        _wrap(
            prune_vectors,
            "prune_vectors",
            "Archive stale vectors in Supabase via rpc_prune_vectors.",
        ),
        _wrap(
            refresh_vector_store,
            "refresh_vector_store",
            "Regenerate embeddings and bulk upsert into signal_embeddings.",
        ),
    ]
    return ToolNode(tools)


def _load_langchain_support() -> dict[str, Any]:
    """Best-effort import of optional LangChain helpers for intent detection."""

    support: dict[str, Any] = {}
    if util.find_spec("langchain_openai") is not None:
        module = import_module("langchain_openai")
        support["ChatOpenAI"] = getattr(module, "ChatOpenAI", None)
    if util.find_spec("langchain_core.prompts") is not None:
        prompts = import_module("langchain_core.prompts")
        support["ChatPromptTemplate"] = getattr(prompts, "ChatPromptTemplate", None)
    return support


def _normalize_state(raw_state: dict[str, Any]) -> PlannerState:
    """Convert arbitrary caller payloads into a PlannerState structure."""

    context = cast(dict[str, Any], raw_state.get("context") or raw_state.get("task_context") or {})
    context_copy = context.copy()
    reserved = {
        "context",
        "task_context",
        "messages",
        "history",
        "results",
        "metrics",
        "guardrail_paths",
        "long_term_state",
        "pending_tool",
        "tool_invocation",
    }
    for key, value in raw_state.items():
        if key not in reserved and key not in ("agent_id",):
            context_copy.setdefault(key, value)
    if not context_copy.get("agent_id") and raw_state.get("agent_id"):
        context_copy["agent_id"] = cast(str, raw_state.get("agent_id"))
    state: PlannerState = {
        "context": context_copy,
        "task_context": context_copy,
        "messages": list(raw_state.get("messages", [])),
        "history": list(raw_state.get("history", [])),
        "results": list(raw_state.get("results", [])),
        "metrics": dict(raw_state.get("metrics", {})),
    }
    if "guardrail_paths" in raw_state:
        state["guardrail_paths"] = list(raw_state.get("guardrail_paths", []))
    if "long_term_state" in raw_state:
        state["long_term_state"] = dict(raw_state.get("long_term_state", {}))
    if "pending_tool" in raw_state:
        state["pending_tool"] = cast(str, raw_state.get("pending_tool"))
    if "tool_invocation" in raw_state:
        state["tool_invocation"] = cast(dict[str, Any], raw_state.get("tool_invocation"))
    return state


def _hydrate_long_term_state(state: PlannerState) -> None:
    if state.get("long_term_state"):
        return
    agent_id = state["context"].get("agent_id")
    if not agent_id:
        return
    try:
        state["long_term_state"] = fetch_agent_state(agent_id)
    except MissingSupabaseConfiguration:
        logger.debug("Supabase not configured; skipping long-term hydration.")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to hydrate long-term state: %s", exc, exc_info=True)


def _detect_intent(request: str) -> str | None:
    lowered = request.lower()
    if any(keyword in lowered for keyword in ("feature", "ts2vec", "encoder")):
        return "propose_new_feature"
    if "backtest" in lowered or "sharpe" in lowered:
        return "run_backtest"
    if "prune" in lowered or "dedupe" in lowered:
        return "prune_vectors"
    if "refresh" in lowered or "reindex" in lowered or "embedding" in lowered:
        return "refresh_vector_store"
    return None


def _plan_node(state: PlannerState, llm_support: dict[str, Any]) -> PlannerState:
    _hydrate_long_term_state(state)

    context = state["context"]
    context.setdefault("requested_at", datetime.utcnow().isoformat())
    request = context.get("intent") or context.get("request")
    if request is None and state["messages"]:
        last_message = state["messages"][-1]
        request = getattr(last_message, "content", str(last_message))
    if not isinstance(request, str):
        raise ValueError("Planner requires a textual intent or request string.")

    intent = _detect_intent(request)
    if intent is None and llm_support.get("ChatOpenAI") and llm_support.get("ChatPromptTemplate"):
        prompt_template = llm_support["ChatPromptTemplate"].from_template(
            "You are a planner for quantitative research agents.\n"
            "Based on the request below, pick one tool to execute next.\n"
            "Return only the name of the tool.\n"
            "Available tools: "
            "propose_new_feature, run_backtest, prune_vectors, "
            "refresh_vector_store.\n"
            "Request: {request}"
        )
        llm = llm_support["ChatOpenAI"](temperature=0, model=context.get("model", "gpt-4o-mini"))
        response = llm.invoke(prompt_template.format_messages(request=request))
        candidate = getattr(response, "content", "")
        if isinstance(candidate, str):
            intent = candidate.strip()

    if intent not in {
        "propose_new_feature",
        "run_backtest",
        "prune_vectors",
        "refresh_vector_store",
    }:
        raise ValueError(f"Unsupported intent '{intent}'.")

    payload = cast(dict[str, Any], context.get("payload") or {})
    tool_invocation = {
        "name": intent,
        "args": {"payload": payload},
        "id": f"{intent}-{uuid4().hex[:8]}",
        "type": "tool_call",
    }
    state["pending_tool"] = intent
    state["tool_invocation"] = tool_invocation
    context["planned_tool"] = intent
    context["planned_at"] = datetime.utcnow().isoformat()
    return state


def _coerce_tool_result(raw: Any) -> Any:
    if isinstance(raw, dict) and "messages" in raw:
        messages = raw.get("messages", [])
    elif isinstance(raw, Iterable) and not isinstance(raw, str | bytes):
        messages = list(raw)
    else:
        messages = [raw]

    payloads: list[Any] = []
    for message in messages:
        content = getattr(message, "content", message)
        if isinstance(content, list):
            flattened = "".join(str(chunk) for chunk in content)
            content = flattened
        if isinstance(content, str):
            try:
                payloads.append(json.loads(content))
                continue
            except json.JSONDecodeError:
                payloads.append(content)
        elif hasattr(message, "additional_kwargs"):
            result = message.additional_kwargs.get("result")
            payloads.append(result if result is not None else content)
        else:
            payloads.append(content)
    if not payloads:
        return None
    if len(payloads) == 1:
        return payloads[0]
    return payloads


def _record_tool_result(state: PlannerState, tool_name: str, payload: Any) -> None:
    record = {
        "tool": tool_name,
        "timestamp": datetime.utcnow().isoformat(),
        "result": payload,
    }
    state.setdefault("results", []).append(record)
    history = state.setdefault("history", [])
    history.append(record)
    state["history"] = history[-HISTORY_WINDOW * 3 :]

    metrics_candidate: dict[str, Any] | None = None
    if isinstance(payload, dict):
        for key in ("result", "metrics"):
            value = payload.get(key)
            if isinstance(value, dict):
                metrics_candidate = value
                break
    if metrics_candidate is not None:
        metrics = state.setdefault("metrics", {})
        metrics[tool_name] = metrics_candidate

    long_term = state.setdefault("long_term_state", {})
    lt_history = long_term.setdefault("history", [])
    lt_history.append(record)
    long_term["history"] = lt_history[-HISTORY_WINDOW * 3 :]
    if metrics_candidate is not None:
        lt_metrics = long_term.setdefault("metrics", {})
        lt_metrics[tool_name] = metrics_candidate
    state["long_term_dirty"] = True


def _execute_tool_node(state: PlannerState, tool_node: ToolNode) -> PlannerState:
    if not state.get("tool_invocation"):
        raise ValueError("No tool invocation prepared for execution.")
    invocation = cast(dict[str, Any], state["tool_invocation"])
    raw_result = tool_node.invoke([
        {
            "name": invocation["name"],
            "args": invocation.get("args", {}),
            "id": invocation.get("id", f"{invocation['name']}-{uuid4().hex[:8]}"),
            "type": invocation.get("type", "tool_call"),
        }
    ])
    payload = _coerce_tool_result(raw_result)
    _record_tool_result(state, invocation["name"], payload)
    state["context"]["last_invoked_tool"] = invocation["name"]
    state["context"]["last_invoked_at"] = datetime.utcnow().isoformat()
    state["pending_tool"] = ""
    state["tool_invocation"] = {}
    return state


def _collect_candidate_paths(result: Any, guardrail_paths: Sequence[str]) -> list[str]:
    candidates: list[str] = []
    if isinstance(result, dict):
        for key in ("file_path", "created_files", "modified_files"):
            value = result.get(key)
            if isinstance(value, str) and value.endswith(".py"):
                candidates.append(value)
            elif isinstance(value, Iterable) and not isinstance(value, str | bytes):
                candidates.extend(str(item) for item in value if str(item).endswith(".py"))
    candidates.extend(str(path) for path in guardrail_paths if str(path).endswith(".py"))
    return sorted({str(path) for path in candidates})


def _run_static_checks(paths: Sequence[str]) -> None:
    if not paths:
        return
    for command in ("ruff", "mypy"):
        try:
            subprocess.run([command, *paths], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            logger.warning("%s is not installed; skipping guardrail.", command)
        except subprocess.CalledProcessError as exc:
            logger.error("%s failed: %s", command, exc.stderr)
            raise RuntimeError(f"Guardrail validation failed during {command}.") from exc


def _guardrail_node(state: PlannerState) -> PlannerState:
    if not state.get("results"):
        return state
    latest_result = state["results"][-1]["result"]
    guardrail_paths = state.get("guardrail_paths", [])
    candidate_paths = _collect_candidate_paths(latest_result, guardrail_paths)
    _run_static_checks(candidate_paths)
    state["validated_paths"] = candidate_paths
    state["context"]["validated_paths"] = candidate_paths
    return state


def _persist_long_term_state(state: PlannerState) -> None:
    if not state.get("long_term_dirty"):
        return
    agent_id = state["context"].get("agent_id")
    if not agent_id:
        return
    try:
        persist_agent_state(agent_id, state.get("long_term_state", {}))
    except MissingSupabaseConfiguration:
        logger.debug("Supabase not configured; skipping long-term persistence.")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to persist long-term state: %s", exc, exc_info=True)
    else:
        state["long_term_dirty"] = False


def _reflection_node(state: PlannerState) -> PlannerState:
    if state.get("results"):
        state["completed"] = True
        state["context"]["completed"] = True
        state["context"]["last_result_summary"] = state["results"][-1]["result"]
    _persist_long_term_state(state)
    return state


def _route_from_plan(state: PlannerState) -> str:
    if state.get("pending_tool"):
        return "invoke_tool"
    return "END"


def build_planner(*, checkpointer: MemorySaver | None = None) -> Any:
    """Compile the LangGraph planner with a persistent checkpointer."""

    tool_node = _build_tool_router()
    llm_support = _load_langchain_support()
    state_graph = StateGraph(PlannerState)
    state_graph.add_node("plan", lambda state: _plan_node(state, llm_support))
    state_graph.add_node("invoke_tool", lambda state: _execute_tool_node(state, tool_node))
    state_graph.add_node("guardrails", _guardrail_node)
    state_graph.add_node("reflect", _reflection_node)
    state_graph.set_entry_point("plan")
    state_graph.add_conditional_edges(
        "plan",
        _route_from_plan,
        {"invoke_tool": "invoke_tool", "END": END},
    )
    state_graph.add_edge("invoke_tool", "guardrails")
    state_graph.add_edge("guardrails", "reflect")
    state_graph.add_edge("reflect", END)
    checkpointer = checkpointer or MemorySaver()
    return state_graph.compile(checkpointer=checkpointer)


_DEFAULT_PLANNER = build_planner()


def run_planner(state: dict[str, Any], *, thread_id: str | None = None) -> PlannerState:
    """Execute the planner end-to-end and return the final state."""

    normalized = _normalize_state(state)
    context = normalized["context"]
    if not context.get("intent") and not context.get("request"):
        return normalized
    planner = _DEFAULT_PLANNER
    thread = thread_id or normalized["context"].get("agent_id") or "local-thread"
    result = planner.invoke(normalized, config={"configurable": {"thread_id": thread}})
    return cast(PlannerState, result)


# Smoke test:
# >>> run_planner({"context": {"intent": "prune_vectors", "payload": {"max_age_days": 1}}})


__all__ = ["PlannerState", "build_planner", "run_planner"]
