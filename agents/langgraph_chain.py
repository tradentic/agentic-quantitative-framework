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
CHECKPOINT_PATH = Path(".cache/langgraph_state.sqlite")


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
    thread_id: str | None = None


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
    """Attempt to load a durable LangGraph checkpointer."""

    try:
        if util.find_spec("langgraph.checkpoint.sqlite") is not None:
            module = import_module("langgraph.checkpoint.sqlite")
            saver_cls = getattr(module, "SqliteSaver", None)
            if saver_cls is not None:
                CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
                if hasattr(saver_cls, "from_conn_string"):
                    return saver_cls.from_conn_string(f"sqlite:///{CHECKPOINT_PATH}")
                return saver_cls(str(CHECKPOINT_PATH))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to initialize SqliteSaver checkpointing: %s", exc, exc_info=True)

    try:
        if util.find_spec("langgraph.checkpoint.memory") is not None:
            module = import_module("langgraph.checkpoint.memory")
            saver_cls = getattr(module, "MemorySaver", None)
            if saver_cls is not None:
                return saver_cls()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("MemorySaver checkpointing unavailable: %s", exc, exc_info=True)

    logger.debug("LangGraph checkpointing unavailable; proceeding without a saver.")
    return None


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
    if not state.thread_id:
        state.thread_id = state.task_context.get("thread_id") or state.task_context.get("agent_id")
    agent_id = state.task_context.get("agent_id") or state.thread_id
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
    commands = {
        "ruff": ["ruff", "check"],
        "mypy": ["mypy"],
    }
    for name, base_command in commands.items():
        try:
            subprocess.run([*base_command, *paths], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            logger.warning("%s is not installed; skipping guardrail check.", name)
        except subprocess.CalledProcessError as exc:
            logger.error("%s failed: %s", name, exc.stderr)
            raise RuntimeError(f"Guardrail validation failed during {name}.") from exc


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
    agent_id = state.task_context.get("agent_id") or state.thread_id
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
    runtime = _load_langgraph_runtime()
    support = _load_langchain_support()
    checkpointer = _load_checkpointer()

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
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    return state_graph.compile(**compile_kwargs)


__all__ = ["AgentState", "build_langgraph_chain"]
