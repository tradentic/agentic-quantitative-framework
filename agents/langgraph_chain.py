"""LangGraph agent orchestration for the Agentic Quantitative Framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module, util
from typing import Any, Callable, Dict, List, Optional

from agents.tools import (
    propose_new_feature,
    prune_vectors,
    refresh_vector_store,
    run_backtest,
)

TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "propose_new_feature": propose_new_feature,
    "run_backtest": run_backtest,
    "prune_vectors": prune_vectors,
    "refresh_vector_store": refresh_vector_store,
}


@dataclass
class AgentState:
    """Shared state that flows between LangGraph nodes."""

    task_context: Dict[str, Any] = field(default_factory=dict)
    messages: List[Any] = field(default_factory=list)
    pending_tool: Optional[str] = None
    tool_input: Dict[str, Any] = field(default_factory=dict)
    results: List[Dict[str, Any]] = field(default_factory=list)


def _load_langgraph_runtime() -> Dict[str, Any]:
    if util.find_spec("langgraph") is None:
        raise ModuleNotFoundError("LangGraph is not installed. Install it with `pip install langgraph`.")
    graph_module = import_module("langgraph.graph")
    return {
        "StateGraph": getattr(graph_module, "StateGraph"),
        "START": getattr(graph_module, "START"),
        "END": getattr(graph_module, "END"),
    }


def _load_langchain_support() -> Dict[str, Any]:
    support: Dict[str, Any] = {}
    if util.find_spec("langchain_openai") is not None:
        module = import_module("langchain_openai")
        support["ChatOpenAI"] = getattr(module, "ChatOpenAI")
    if util.find_spec("langchain_core.prompts") is not None:
        prompts = import_module("langchain_core.prompts")
        support["ChatPromptTemplate"] = getattr(prompts, "ChatPromptTemplate")
    return support


def _detect_intent(request: str) -> Optional[str]:
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


def _plan_node(state: AgentState, llm_support: Dict[str, Any]) -> AgentState:
    context_request = state.task_context.get("intent") or state.task_context.get("request")
    if context_request is None and state.messages:
        last_message = state.messages[-1]
        context_request = getattr(last_message, "content", str(last_message))
    if context_request is None:
        raise ValueError("AgentState is missing a task request for planning.")

    intent = _detect_intent(context_request)
    if intent is None and "ChatOpenAI" in llm_support and "ChatPromptTemplate" in llm_support:
        prompt_template = llm_support["ChatPromptTemplate"].from_template(
            (
                "You are an orchestration planner for a quantitative research agent.\n"
                "Decide which tool should be invoked based on the user request.\n"
                "Available tools: propose_new_feature, run_backtest, prune_vectors, refresh_vector_store.\n"
                "Return only the tool name."
            )
        )
        llm = llm_support["ChatOpenAI"](temperature=0, model=state.task_context.get("model", "gpt-4o-mini"))
        response = llm.invoke(prompt_template.format_messages(request=context_request))
        intent = getattr(response, "content", "").strip()

    if intent not in TOOL_REGISTRY:
        raise ValueError(f"Unsupported intent '{intent}'. Available tools: {list(TOOL_REGISTRY)}")

    state.pending_tool = intent
    state.tool_input = state.task_context.get("payload", {})
    return state


def _execute_tool_node(state: AgentState) -> AgentState:
    tool_name = state.pending_tool
    if tool_name is None:
        raise ValueError("No pending tool selected in the agent state.")
    tool = TOOL_REGISTRY[tool_name]
    result = tool(state.tool_input)
    state.results.append(result)
    state.pending_tool = None
    state.tool_input = {}
    return state


def _reflection_node(state: AgentState) -> AgentState:
    if not state.results:
        return state
    latest = state.results[-1]
    status = latest.get("result") or latest.get("record")
    state.task_context["last_result_summary"] = status
    state.task_context["completed"] = True
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

    state_graph = runtime["StateGraph"](AgentState)
    state_graph.add_node("plan", lambda state: _plan_node(state, support))
    state_graph.add_node("execute_tool", _execute_tool_node)
    state_graph.add_node("reflect", _reflection_node)
    state_graph.set_entry_point("plan")
    state_graph.add_conditional_edges("plan", _route_from_plan, {"execute_tool": "execute_tool", "END": runtime["END"]})
    state_graph.add_edge("execute_tool", "reflect")
    state_graph.add_conditional_edges("reflect", _route_from_reflection, {"END": runtime["END"], "plan": "plan"})
    return state_graph.compile()


__all__ = ["AgentState", "build_langgraph_chain"]
