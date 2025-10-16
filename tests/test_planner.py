from agents.langgraph_chain import QuantitativePlanner

def test_quantitative_planner_returns_state():
    planner = QuantitativePlanner()
    state = planner.invoke("Improve mean-reversion alpha")
    assert state.objective == "Improve mean-reversion alpha"
    assert state.feature_plan
    assert state.backtest_result
    assert state.vector_actions
    assert any("Backtest" in note for note in state.notes)
