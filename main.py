from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.agents import planner_agent, coder_agent
from src.executor import executor_agent
from src.researcher import researcher_agent

# --- Logic for Looping ---
def should_continue(state: AgentState):
    result = state['review']
    if "SUCCESS" in result: return "end"
    if state['revision_number'] >= state['max_revisions']: return "end"
    return "research"

# --- Build the Graph ---
workflow = StateGraph(AgentState)
workflow.add_node("planner", planner_agent)
workflow.add_node("coder", coder_agent)
workflow.add_node("executor", executor_agent)
workflow.add_node("researcher", researcher_agent)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "coder")
workflow.add_edge("coder", "executor")
workflow.add_edge("researcher", "coder")

workflow.add_conditional_edges("executor", should_continue, {
    "research": "researcher",
    "end": END
})

# NOTE: We do NOT compile it here anymore. 
# We export the 'workflow' blueprint to app.py