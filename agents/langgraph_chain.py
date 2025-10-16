"""LangGraph agent orchestration for the Agentic Quantitative Framework."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from importlib import import_module, util
from pathlib import Path
from typing import Any

from framework.supabase_client import (
    MissingSupabaseConfiguration,
    fetch_agent_state,
    persist_agent_state,
)

from agents.tools import (
    propose_new_feature,
    prune_vectors,
    refresh_vector_store,
    run_backtest,
)

logger = logging.getLogger(__name__)

TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "propose_new_feature": propose_new_feature,
    "run_backtest": run_backtest,
    "prune_vectors": prune_vectors,
    "refresh_vector_store": refresh_vector_store,
}

SHORT_TERM_WINDOW = 5


@dataclass
class AgentState:
    """Shared state that flows between LangGraph nodes."""

    task_context: dict[str, Any] = field(default_factory=dict)
    messages: list[Any] = field(default_factory=list)
    pending_tool: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    short_term_memory: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    long_term_state: dict[str, Any] = field(default_factory=dict)
    long_term_dirty: bool = False


def _load_langgraph_runtime() -> dict[str, Any]:
    if util.find_spec("langgraph") is None:
        raise ModuleNotFoundError(
            "LangGraph is not installed. Install it with `pip install langgraph`."
        )
    graph_module = import_module("langgraph.graph")
    return {
        "StateGraph": graph_module.StateGraph,
        "START": graph_module.START,
        "END": graph_module.END,
    }


def _load_langchain_support() -> dict[str, Any]:
    support: dict[str, Any] = {}
    if util.find_spec("langchain_openai") is not None:
        module = import_module("langchain_openai")
        support["ChatOpenAI"] = module.ChatOpenAI
    if util.find_spec("langchain_core.prompts") is not None:
        prompts = import_module("langchain_core.prompts")
        support["ChatPromptTemplate"] = prompts.ChatPromptTemplate
    return support


def _load_checkpointer() -> Any | None:
    """Return a LangGraph checkpointer implementation when available."""

    try:
        module = import_module("langgraph.checkpoint.memory")
    except ModuleNotFoundError:
        logger.debug(
            "LangGraph checkpoint memory module not available; "
            "falling back to stateless execution.",
        )
        return None
    return getattr(module, "MemorySaver", None)


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


def _hydrate_long_term_state(state: AgentState) -> None:
    if state.long_term_state:
        return
    agent_id = state.task_context.get("agent_id")
    if not agent_id:
        return
    try:
        state.long_term_state = fetch_agent_state(agent_id)
    except MissingSupabaseConfiguration:
        logger.debug("Supabase is not configured; skipping long-term state hydration.")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to hydrate long-term state: %s", exc, exc_info=True)


def _plan_node(state: AgentState, llm_support: dict[str, Any]) -> AgentState:
    _hydrate_long_term_state(state)

    context_request = state.task_context.get("intent") or state.task_context.get("request")
    if context_request is None and state.messages:
        last_message = state.messages[-1]
        context_request = getattr(last_message, "content", str(last_message))
    if context_request is None:
        raise ValueError("AgentState is missing a task request for planning.")

    intent = _detect_intent(context_request)
    if intent is None and "ChatOpenAI" in llm_support and "ChatPromptTemplate" in llm_support:
        prompt_template = llm_support["ChatPromptTemplate"].from_template(
            "You are an orchestration planner for a quantitative research agent.\n"
            "Decide which tool should be invoked based on the user request.\n"
            "Available tools: propose_new_feature, run_backtest, prune_vectors,\n"
            "refresh_vector_store.\n"
            "Return only the tool name."
        )
        llm = llm_support["ChatOpenAI"](
            temperature=0,
            model=state.task_context.get("model", "gpt-4o-mini"),
        )
        response = llm.invoke(prompt_template.format_messages(request=context_request))
        intent = getattr(response, "content", "").strip()

    if intent not in TOOL_REGISTRY:
        raise ValueError(f"Unsupported intent '{intent}'. Available tools: {list(TOOL_REGISTRY)}")

    state.pending_tool = intent
    state.tool_input = state.task_context.get("payload", {})
    return state


def _record_tool_call(state: AgentState, tool_name: str, result: dict[str, Any]) -> None:
    entry = {
        "tool": tool_name,
        "timestamp": datetime.utcnow().isoformat(),
        "result": result.get("result") or result,
    }
    state.short_term_memory.append(entry)
    state.short_term_memory = state.short_term_memory[-SHORT_TERM_WINDOW:]
    history = state.long_term_state.setdefault("history", [])
    history.append(entry)
    state.long_term_state["history"] = history[-SHORT_TERM_WINDOW * 3 :]
    state.long_term_dirty = True


def _update_metrics(state: AgentState, tool_name: str, result: dict[str, Any]) -> None:
    metrics_payload = result.get("result")
    if isinstance(metrics_payload, dict):
        state.metrics[tool_name] = metrics_payload
        metrics_state = state.long_term_state.setdefault("metrics", {})
        metrics_state[tool_name] = metrics_payload
        state.long_term_dirty = True


def _execute_tool_node(state: AgentState) -> AgentState:
    tool_name = state.pending_tool
    if tool_name is None:
        raise ValueError("No pending tool selected in the agent state.")
    tool = TOOL_REGISTRY[tool_name]
    result = tool(state.tool_input)
    state.results.append(result)
    _record_tool_call(state, tool_name, result)
    _update_metrics(state, tool_name, result)
    state.pending_tool = None
    state.tool_input = {}
    return state


def _collect_candidate_paths(result: dict[str, Any], guardrail_paths: Sequence[str]) -> list[str]:
    candidates: list[str] = []
    file_path = result.get("file_path")
    if isinstance(file_path, str) and file_path.endswith(".py"):
        candidates.append(file_path)
    for key in ("created_files", "modified_files"):
        value = result.get(key)
        if isinstance(value, str):
            candidates.append(value)
        elif isinstance(value, Iterable):
            candidates.extend(str(item) for item in value if isinstance(item, str))
    candidates.extend(str(path) for path in guardrail_paths)
    return sorted({str(Path(path)) for path in candidates if str(path).endswith(".py")})


def _run_static_checks(paths: Sequence[str]) -> None:
    if not paths:
        return
    for command in ("ruff", "mypy"):
        try:
            subprocess.run([command, *paths], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            logger.warning("%s is not installed; skipping guardrail check.", command)
        except subprocess.CalledProcessError as exc:
            logger.error("%s failed: %s", command, exc.stderr)
            raise RuntimeError(f"Guardrail validation failed during {command}.") from exc


def _guardrail_node(state: AgentState) -> AgentState:
    if not state.results:
        return state
    guardrail_paths = state.task_context.get("guardrail_paths", [])
    latest_result = state.results[-1]
    candidate_paths = _collect_candidate_paths(latest_result, guardrail_paths)
    _run_static_checks(candidate_paths)
    state.task_context["validated_paths"] = candidate_paths
    return state


def _persist_long_term_state(state: AgentState) -> None:
    if not state.long_term_dirty:
        return
    agent_id = state.task_context.get("agent_id")
    if not agent_id:
        return
    try:
        persist_agent_state(agent_id, state.long_term_state)
    except MissingSupabaseConfiguration:
        logger.debug("Supabase is not configured; skipping long-term state persistence.")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to persist long-term state: %s", exc, exc_info=True)
    else:
        state.long_term_dirty = False


def _reflection_node(state: AgentState) -> AgentState:
    if not state.results:
        return state
    latest = state.results[-1]
    status = latest.get("result") or latest.get("record")
    state.task_context["last_result_summary"] = status
    state.task_context["completed"] = True
    _persist_long_term_state(state)
    return state


def _route_from_plan(state: AgentState) -> str:
    if state.pending_tool:
        return "execute_tool"
    return "END"


def _route_from_reflection(state: AgentState) -> str:
    if state.task_context.get("completed"):
        return "END"
    return "plan"


def build_langgraph_chain() -> Any:
    """Return a stateful LangGraph planner with checkpointing and tool routing."""

    runtime = _load_langgraph_runtime()
    support = _load_langchain_support()
    memory_factory = _load_checkpointer()

    state_graph = runtime["StateGraph"](AgentState)
    state_graph.add_node("plan", lambda state: _plan_node(state, support))
    state_graph.add_node("execute_tool", _execute_tool_node)
    state_graph.add_node("guard", _guardrail_node)
    state_graph.add_node("reflect", _reflection_node)
    state_graph.set_entry_point("plan")
    state_graph.add_conditional_edges(
        "plan",
        _route_from_plan,
        {"execute_tool": "execute_tool", "END": runtime["END"]},
    )
    state_graph.add_edge("execute_tool", "guard")
    state_graph.add_edge("guard", "reflect")
    state_graph.add_conditional_edges(
        "reflect",
        _route_from_reflection,
        {"END": runtime["END"], "plan": "plan"},
    )

    compile_kwargs: dict[str, Any] = {}
    if callable(memory_factory):
        compile_kwargs["checkpointer"] = memory_factory()

    chain = state_graph.compile(**compile_kwargs)
    if hasattr(chain, "config"):
        # Expose tool metadata so callers can introspect supported operations when resuming threads.
        chain.config = {
            "tools": sorted(TOOL_REGISTRY),
            "short_term_window": SHORT_TERM_WINDOW,
        }
    return chain


__all__ = ["AgentState", "build_langgraph_chain"]
