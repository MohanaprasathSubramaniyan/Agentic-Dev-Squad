import os
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
from src.state import AgentState

load_dotenv()

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    temperature=0
)

def planner_agent(state: AgentState):
    print("--- PLANNER IS THINKING ---")
    messages = [
        SystemMessage(content="You are a Senior Technical Lead. Break the task into implementation steps."),
        HumanMessage(content=state['task'])
    ]
    response = llm.invoke(messages)
    return {"plan": response.content, "revision_number": 1, "max_revisions": 3}

def coder_agent(state: AgentState):
    print("--- CODER IS WRITING ---")
    
    task = state['task']
    plan = state['plan']
    review = state.get('review', "")
    
    # Prompt Logic
    if review and "SyntaxError" in review:
        print(f"--- FIXING BUG (Attempt {state['revision_number']}) ---")
        content = (f"The previous code crashed.\nError: {review}\n"
                   f"TASK: Fix the code. Ensure all file paths are quoted strings.\n"
                   f"Original Task: {task}")
    else:
        content = f"Task: {task}\n\nPlan: {plan}\nOutput ONLY pure Python code."

    messages = [
        SystemMessage(content="You are a Python Developer. Output ONLY executable Python code."),
        HumanMessage(content=content)
    ]
    
    response = llm.invoke(messages)
    clean_code = response.content.replace("```python", "").replace("```", "").strip()
    
    # --- GUARD RAIL: AUTO-FIX THE PATH ERROR ---
    # If the AI forgets quotes around the specific file, we add them manually.
    target_file = "/mnt/data/Telco-Customer-Churn.csv"
    if target_file in clean_code:
        # Check if it's NOT quoted (simple check)
        if f"'{target_file}'" not in clean_code and f'"{target_file}"' not in clean_code:
            print("--- GUARD RAIL ACTIVATED: Adding missing quotes to file path ---")
            clean_code = clean_code.replace(target_file, f"'{target_file}'")
            
    return {"code": clean_code}