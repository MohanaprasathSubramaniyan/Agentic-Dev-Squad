import sqlite3

# Connect to the database (it will create the file if it doesn't exist)
conn = sqlite3.connect('chainlit.db')
c = conn.cursor()

print("🔧 Repairing Database...")

# 1. Create 'users' table (This is the one causing your error!)
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL UNIQUE,
    createdAt TEXT,
    metadata TEXT
);
''')

# 2. Create 'threads' table (For chat history)
c.execute('''
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    createdAt TEXT,
    name TEXT,
    userId TEXT,
    userIdentifier TEXT,
    tags TEXT,
    metadata TEXT
);
''')

# 3. Create 'steps' table (For messages)
c.execute('''
CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    threadId TEXT,
    parentId TEXT,
    disableFeedback INTEGER,
    streaming INTEGER,
    waitForAnswer INTEGER,
    isError INTEGER,
    metadata TEXT,
    tags TEXT,
    input TEXT,
    output TEXT,
    createdAt TEXT,
    start TEXT,
    end TEXT,
    generation TEXT,
    showInput TEXT,
    language TEXT,
    indent INTEGER
);
''')

# 4. Create 'elements' table (For file uploads/images)
c.execute('''
CREATE TABLE IF NOT EXISTS elements (
    id TEXT PRIMARY KEY,
    threadId TEXT,
    type TEXT,
    url TEXT,
    chainlitKey TEXT,
    name TEXT,
    display TEXT,
    size TEXT,
    language TEXT,
    page INTEGER,
    mime TEXT,
    path TEXT
);
''')

conn.commit()
conn.close()
print("✅ Database tables created successfully!")