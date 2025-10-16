from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any


@dataclass
class _AgentState:
    task_context: dict[str, Any]
    messages: list[Any]


class _LangGraphChain:
    def invoke(self, state: _AgentState) -> _AgentState:
        return state


def _build_langgraph_chain() -> _LangGraphChain:
    return _LangGraphChain()


agents_module = sys.modules.setdefault("agents", types.ModuleType("agents"))
setattr(agents_module, "langgraph_chain", types.ModuleType("agents.langgraph_chain"))
setattr(agents_module.langgraph_chain, "AgentState", _AgentState)
setattr(agents_module.langgraph_chain, "build_langgraph_chain", _build_langgraph_chain)
sys.modules["agents.langgraph_chain"] = agents_module.langgraph_chain

agents_tools = sys.modules.setdefault("agents.tools", types.ModuleType("agents.tools"))
setattr(agents_tools, "run_backtest", lambda config: None)
setattr(agents_tools, "poll_embedding_jobs", lambda limit=5: [])
setattr(agents_tools, "refresh_vector_store", lambda jobs: jobs)
setattr(agents_tools, "prune_vectors", lambda limit=5: [])
sys.modules["agents.tools"] = agents_tools
