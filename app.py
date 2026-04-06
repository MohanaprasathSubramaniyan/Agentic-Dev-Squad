import chainlit as cl
import os
import shutil
import sqlite3
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from langgraph.checkpoint.memory import MemorySaver 
from main import workflow

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Use a folder named 'data' for all inputs and outputs
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
    
    await cl.Message(
        author="Agent Squad", 
        content="**Hello!** 👋\n\nI am your Agentic Data Team. Upload a CSV/Excel file, and I will analyze it and generate charts for you!"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    # Handle File Uploads
    if message.elements:
        file_element = message.elements[0]
        dest_path = os.path.join(DATA_DIR, file_element.name)
        shutil.copy(file_element.path, dest_path)
        cl.user_session.set("current_file", file_element.name)
        await cl.Message(author="System", content=f"📂 **File Uploaded:** `{file_element.name}`").send()

    current_file = cl.user_session.get("current_file")
    chart_path = os.path.join(DATA_DIR, "chart.png")
    
    # Clean up old charts before starting
    if os.path.exists(chart_path):
        os.remove(chart_path)

    if current_file:
        file_path = os.path.join(DATA_DIR, current_file)
        # We tell the agent specifically to use the relative 'data/chart.png' path
        data_context = (
            f"\n\nCONTEXT: Dataset located at '{file_path}'. "
            f"Please save any generated charts strictly to 'data/chart.png'. "
            "Use 'plt.savefig(data/chart.png)' and DO NOT use 'plt.show()'."
        )
    else:
        data_context = "\n\nCONTEXT: No file uploaded yet. Ask the user for a dataset."

    task = message.content + data_context
    await cl.Message(author="Manager", content="Starting the engine...").send()
    
    thread_id = cl.user_session.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}
    app = workflow.compile(checkpointer=memory)
    
    async for output in app.astream({"task": task}, config=config):
        for node_name, node_state in output.items():
            if node_name == "planner":
                await cl.Message(author="Planner", content=f"**Plan:**\n{node_state['plan']}").send()
            
            elif node_name == "coder":
                await cl.Message(author="Coder", language="python", content=node_state['code']).send()
            
            elif node_name == "executor":
                review = node_state['review']
                
                # VITAL: Check if the Agent actually created the file in the data folder
                if os.path.exists(chart_path):
                    # We send the image as an element to the UI
                    image = cl.Image(path=chart_path, name="Analysis Chart", display="inline")
                    await cl.Message(
                        author="Executor", 
                        content="📊 **Visual Analysis Complete:**", 
                        elements=[image]
                    ).send()
                
                if "SUCCESS" in review:
                    await cl.Message(author="Executor", content=f"✅ **Execution Summary:**\n{review}").send()
                else:
                    await cl.Message(author="Executor", content=f"❌ **Debugger Alert:**\n{review}").send()
    
    await cl.Message(author="Manager", content="Workflow Finished.").send()
