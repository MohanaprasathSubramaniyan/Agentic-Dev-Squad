import docker
import os
from src.state import AgentState

def executor_agent(state: AgentState):
    print("--- EXECUTOR IS RUNNING CODE ---")
    
    code = state['code']
    client = docker.from_env()
    
    # 1. Get absolute path to the 'data' folder
    work_dir = os.getcwd()
    data_dir = os.path.join(work_dir, "data")
    
    try:
        # 2. Run container safely
        container = client.containers.run(
            image="ds-executor",
            command=["python", "-c", code],
            volumes={
                data_dir: {'bind': '/mnt/data', 'mode': 'rw'}
            },
            detach=False,
            stdout=True,
            stderr=True,
            remove=True
        )
        
        # 3. Capture the actual print() output from the script
        output = container.decode('utf-8')
        print(f"OUTPUT: {output}")
        
        # --- THE FIX IS HERE ---
        # Instead of just returning "SUCCESS", we return "SUCCESS" + the output text.
        return {
            "review": f"SUCCESS\n\nOUTPUT:\n{output}", 
            "revision_number": state['revision_number']
        }

    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'stderr') and e.stderr:
            error_msg = e.stderr.decode('utf-8')
            
        print(f"CRASH DETECTED: {error_msg}")
        return {
            "review": f"ERROR: {error_msg}", 
            "revision_number": state['revision_number'] + 1
        }