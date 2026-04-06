import chainlit as cl
import os
import shutil
import sqlite3
import subprocess
import sys
import pandas as pd
import time
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from langgraph.checkpoint.memory import MemorySaver 
from main import workflow

# --- CONFIGURATION ---
BASE_DIR = "/home/user/app" # Fixed Hugging Face Path
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

CHAINLIT_DB_PATH = os.path.join(BASE_DIR, "chainlit.db")
CHAINLIT_CONN_STRING = f"sqlite+aiosqlite:///{CHAINLIT_DB_PATH}"

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

memory = MemorySaver()

@cl.on_chat_start
async def start():
    cl.user_session.set("thread_id", cl.context.session.id)
    cl.user_session.set("current_file", None)
    await cl.Message(author="Agent Squad", content="**Engine Active.** 🚀\nI'm ready to visualize your data.").send()

@cl.on_message
async def main(message: cl.Message):
    if message.elements:
        file_element = message.elements[0]
        dest_path = os.path.join(DATA_DIR, file_element.name)
        shutil.copy(file_element.path, dest_path)
        cl.user_session.set("current_file", file_element.name)
        await cl.Message(author="System", content=f"📂 **File Uploaded:** `{file_element.name}`").send()

    current_file = cl.user_session.get("current_file")
    
    # Create a unique path for THIS specific chart request
    chart_filename = f"chart_{int(time.time())}.png"
    abs_chart_path = os.path.join(DATA_DIR, chart_filename)

    if current_file:
        abs_data_path = os.path.join(DATA_DIR, current_file)
        try:
            df_temp = pd.read_csv(abs_data_path, nrows=1)
            col_info = f"Columns available: {df_temp.columns.tolist()}."
        except:
            col_info = ""

        data_context = (
            f"\n\nCONTEXT: Use the dataset at '{abs_data_path}'. {col_info} "
            f"STRICT INSTRUCTION: You MUST save your plot to exactly '{abs_chart_path}'. "
            "Use 'plt.savefig' and 'plt.close()'. Write only straight-line execution code."
        )
    else:
        data_context = "\n\nCONTEXT: Ask the user to upload a file."

    task = message.content + data_context
    await cl.Message(author="Manager", content="Processing request...").send()
    
    config = {"configurable": {"thread_id": cl.user_session.get("thread_id")}}
    app = workflow.compile(checkpointer=memory)
    
    async for output in app.astream({"task": task}, config=config):
        for node_name, node_state in output.items():
            if node_name == "coder":
                raw_code = node_state['code']
                await cl.Message(author="Coder", language="python", content=raw_code).send()
                
                try:
                    clean_code = raw_code.replace("```python", "").replace("```", "").strip()
                    script_path = os.path.join(BASE_DIR, "temp_script.py")
                    with open(script_path, "w") as f:
                        f.write(clean_code)
                    
                    proc = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=30)
                    if proc.stderr:
                        await cl.Message(author="System", content=f"❌ **Python Error:**\n{proc.stderr}").send()
                    if proc.stdout:
                        await cl.Message(author="System", content=f"💬 **Output:**\n{proc.stdout}").send()
                except Exception as e:
                    await cl.Message(author="System", content=f"⚠️ **Fail:** {str(e)}").send()
            
            elif node_name == "executor":
                # Final attempt to find the chart
                found = False
                for _ in range(15): # Wait up to 7.5 seconds
                    if os.path.exists(abs_chart_path):
                        found = True
                        break
                    time.sleep(0.5)

                if found:
                    image = cl.Image(path=abs_chart_path, name="Chart", display="inline")
                    await cl.Message(author="Executor", content="📊 **Analysis Results:**", elements=[image]).send()
                else:
                    await cl.Message(author="Executor", content="✅ **Analysis complete, but no chart was saved to the disk.**").send()
    
    await cl.Message(author="Manager", content="Finished.").send()
