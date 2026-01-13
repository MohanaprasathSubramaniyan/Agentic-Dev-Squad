from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState

def researcher_agent(state: AgentState):
    print("--- RESEARCHER IS INVESTIGATING ---")
    
    error = state['review']
    task = state['task']
    
    # 1. Initialize the Search Tool
    tool = TavilySearchResults(max_results=3)
    
    # 2. CLEAN THE QUERY: Remove newlines and truncate to avoid 400 Bad Request
    clean_error = error.replace("\n", " ").replace("  ", " ")[:200]
    query = f"Python syntax error {clean_error} fix"
    
    try:
        results = tool.invoke(query)
        
        # 3. Robust Parsing (Handle different return types)
        findings = ""
        if isinstance(results, str):
            findings = results
        elif isinstance(results, list):
            for r in results:
                if isinstance(r, dict):
                    findings += f"- {r.get('content', str(r))}\n"
                else:
                    findings += f"- {str(r)}\n"
        else:
            findings = str(results)
            
    except Exception as e:
        findings = f"Research failed with error: {str(e)}"

    print(f"--- RESEARCH FOUND INSIGHTS ---\n{findings[:200]}...") 
    
    # 4. Save the research into the state
    return {"plan": f"PREVIOUS ERROR FIX INSTRUCTIONS:\n{findings}\n\nORIGINAL PLAN:\n{state['plan']}"}