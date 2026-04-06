import chainlit as cl
import os
import shutil
import sqlite3
import subprocess
import sys
import pandas as pd
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from langgraph.checkpoint.memory import MemorySaver 
from main import workflow

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

CHAINLIT_DB_PATH = os.path.join(BASE_DIR, "chainlit.db")
CHAINLIT_CONN_STRING = f"sqlite+aiosqlite:///{CHAINLIT_DB_PATH}"

# --- DATABASE INIT ---
def init_db():
    conn = sqlite3.connect(CHAINLIT_DB_PATH)
    c = conn.cursor()
    tables = [
        '''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, identifier TEXT NOT NULL UNIQUE, createdAt TEXT, metadata TEXT);''',
        '''CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, createdAt TEXT, name TEXT, userId TEXT, userIdentifier TEXT, tags TEXT, metadata TEXT);''',
        '''CREATE TABLE IF NOT EXISTS steps (id TEXT PRIMARY KEY, name TEXT, type TEXT, threadId TEXT, parentId TEXT, disableFeedback INTEGER, streaming INTEGER, waitForAnswer INTEGER, isError INTEGER, metadata TEXT, tags TEXT, input TEXT, output TEXT, createdAt TEXT, start TEXT, end TEXT, generation TEXT, showInput TEXT, language TEXT, indent INTEGER, defaultOpen INTEGER);''',
        '''CREATE TABLE IF NOT EXISTS elements (id TEXT PRIMARY KEY, threadId TEXT, type TEXT, url TEXT, chainlitKey TEXT, name TEXT, display TEXT, size TEXT, language TEXT, page INTEGER, mime TEXT, path TEXT, objectKey TEXT, forId TEXT, props TEXT);''',
        '''CREATE TABLE IF NOT EXISTS feedbacks (id TEXT PRIMARY KEY, forId TEXT, value INTEGER, comment TEXT, strategy TEXT);'''
    ]
    for query in tables:
        c.execute(query)
    conn.commit()
    conn.close()

init_db()

@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=CHAINLIT_CONN_STRING)

# --- GLOBAL MEMORY ---
memory = MemorySaver()

@cl.on_chat_start
async def start():
    cl.user_session.set("thread_id", cl.context.session.id)
    cl.user_session.set("current_file", None)
    await cl.Message(author="Agent Squad", content="**Engine Online.** 🚀\nUpload your CSV, and I'll analyze the real columns to generate your charts.").send()

@cl.on_message
async def main(message: cl.Message):
    # 1. Handle File Uploads
    if message.elements:
        file_element = message.elements[0]
        dest_path = os.path.join(DATA_DIR, file_element.name)
        shutil.copy(file_element.path, dest_path)
        cl.user_session.set("current_file", file_element.name)
        await cl.Message(author="System", content=f"📂 **File Uploaded:** `{file_element.name}`").send()

    current_file = cl.user_session.get("current_file")
    abs_chart_path = os.path.join(DATA_DIR, "chart.png")
    
    # 2. Cleanup old charts
    if os.path.exists(abs_chart_path):
        os.remove(abs_chart_path)

    # 3. Build Context with REAL Column Names
    if current_file:
        abs_data_path = os.path.join(DATA_DIR, current_file)
        
        # READ HEADERS TO PREVENT HALLUCINATION
        try:
            df_temp = pd.read_csv(abs_data_path, nrows=1)
            columns = df_temp.columns.tolist()
            col_info = f"The ACTUAL columns in this file are: {columns}."
        except Exception:
            col_info = "Could not read columns. Please ask the user for column names."

        data_context = (
            f"\n\nCONTEXT: Use the dataset at '{abs_data_path}'. "
            f"{col_info} "
            f"STRICT RULE: Do NOT use placeholders like 'feature_name'. Use the real columns listed above. "
            f"Save your plot ONLY to '{abs_chart_path}'. "
            "Use 'plt.savefig' and 'plt.close()'. Do NOT use 'plt.show()'. "
            "IMPORTANT: Write the code to execute immediately, do not just wrap it in a function."
        )
    else:
        data_context = "\n\nCONTEXT: Tell the user to upload a dataset first."

    # 4. Run LangGraph Workflow
    task = message.content + data_context
    await cl.Message(author="Manager", content="Orchestrating agents...").send()
    
    thread_id = cl.user_session.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}
    app = workflow.compile(checkpointer=memory)
    
    async for output in app.astream({"task": task}, config=config):
        for node_name, node_state in output.items():
            if node_name == "planner":
                await cl.Message(author="Planner", content=f"**Plan:**\n{node_state['plan']}").send()
            
            elif node_name == "coder":
                raw_code = node_state['code']
                await cl.Message(author="Coder", language="python", content=raw_code).send()
                
                # --- EXECUTION LOGIC ---
                try:
                    # Clean the code (remove markdown blocks)
                    clean_code = raw_code.replace("```python", "").replace("```", "").strip()
                    script_path = os.path.join(BASE_DIR, "temp_script.py")
                    
                    with open(script_path, "w") as f:
                        f.write(clean_code)
                    
                    # Execute
                    result = subprocess.run(
                        [sys.executable, script_path], 
                        capture_output=True, 
                        text=True, 
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        await cl.Message(author="System", content=f"⚠️ **Execution Error:**\n{result.stderr}").send()
                except Exception as e:
                    await cl.Message(author="System", content=f"⚠️ **System Error:** {str(e)}").send()
            
            elif node_name == "executor":
                # Final Check: Does the chart exist?
                if os.path.exists(abs_chart_path):
                    image = cl.Image(path=abs_chart_path, name="Analysis Chart", display="inline")
                    await cl.Message(author="Executor", content="📊 **Visualization Generated:**", elements=[image]).send()
                else:
                    review = node_state.get('review', 'No review provided.')
                    await cl.Message(author="Executor", content=f"✅ **Analysis Complete:**\n{review}").send()
    
    await cl.Message(author="Manager", content="Task finalized.").send()
