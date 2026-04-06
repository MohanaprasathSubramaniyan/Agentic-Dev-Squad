import chainlit as cl
import os
import shutil
import sqlite3
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from langgraph.checkpoint.memory import MemorySaver 
from main import workflow

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAINLIT_DB_PATH = os.path.join(BASE_DIR, "chainlit.db")
CHAINLIT_CONN_STRING = f"sqlite+aiosqlite:///{CHAINLIT_DB_PATH}"

# --- SELF-HEALING DATABASE LOGIC (Chainlit Only) ---
def init_db():
    """Initialize Chainlit Database Tables."""
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

# Run Init
init_db()

# --- APP SETUP ---
@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=CHAINLIT_CONN_STRING)

# --- AUTHENTICATION REMOVED ---
# The @cl.password_auth_callback block has been deleted to allow public access.

os.makedirs("data", exist_ok=True)

# --- GLOBAL MEMORY ---
memory = MemorySaver()

@cl.on_chat_start
async def start():
    # Since login is removed, we set a default identifier
    user_display_name = "Admin" 
    
    thread_id = cl.context.session.id
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("current_file", None)
    
    await cl.Message(
        author="Agent Squad", 
        content=f"**Hello {user_display_name}!** 👋\n\nI am your AI Data Team.\nUpload a file and ask me to analyze your data!"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    if message.elements:
        file_element = message.elements[0]
        source_path = file_element.path
        dest_path = os.path.join("data", file_element.name)
        shutil.copy(source_path, dest_path)
        cl.user_session.set("current_file", file_element.name)
        await cl.Message(author="System", content=f"📂 **File Uploaded:** `{file_element.name}`").send()

    current_file = cl.user_session.get("current_file")
    if current_file:
        file_path = f"data/{current_file}"
        data_context = (
            f"\n\nCONTEXT: Dataset at '{file_path}'. "
            f"file_path = '{file_path}'. "
            "Do NOT use sample data. Save charts to 'data/chart.png'. Do NOT use plt.show()."
        )
    else:
        data_context = "\n\nCONTEXT: Ask the user to upload a file first."

    task = message.content + data_context
    if os.path.exists("data/chart.png"): 
        os.remove("data/chart.png")
    
    await cl.Message(author="Manager", content=f"Starting task...").send()
    
    thread_id = cl.user_session.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}
    
    # COMPILE WITH MEMORY SAVER
    app = workflow.compile(checkpointer=memory)
    
    async for output in app.astream({"task": task}, config=config):
        for node_name, node_state in output.items():
            if node_name == "planner":
                await cl.Message(author="Planner", content=f"**Plan:**\n{node_state['plan']}").send()
            elif node_name == "researcher":
                await cl.Message(author="Researcher", content=f"🔍 **Research:**\n{node_state['plan']}").send()
            elif node_name == "coder":
                code = node_state['code']
                await cl.Message(author="Coder", language="python", content=code).send()
            elif node_name == "executor":
                review = node_state['review']
                if os.path.exists("data/chart.png"):
                    image = cl.Image(path="data/chart.png", name="chart", display="inline")
                    await cl.Message(author="Executor", content="✅ **Chart Generated:**", elements=[image]).send()
                elif "SUCCESS" in review:
                    await cl.Message(author="Executor", content=f"✅ **Result:**\n{review}").send()
                else:
                    await cl.Message(author="Executor", content=f"❌ **Error:**\n{review}").send()
    
    await cl.Message(author="Manager", content="Process Complete.").send()
