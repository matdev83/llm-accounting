import pytest
from llm_accounting.backends.sqlite import SQLiteBackend
import sqlite3
import typing

@pytest.fixture
def test_db():
    """Fixture setting up an in-memory test database with sample data"""
    backend = SQLiteBackend("file:memdb.sqlite?mode=memory&cache=shared")
    backend.initialize()
    conn = typing.cast(sqlite3.Connection, backend.conn)
    
    # Create fresh connection and explicit schema
    conn.close()
    shared_conn = sqlite3.connect("file:memdb.sqlite?mode=memory&cache=shared", uri=True)
    
    shared_conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounting_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            username TEXT,
            datetime TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            cost REAL NOT NULL DEFAULT 0.0,
            execution_time REAL NOT NULL DEFAULT 0.0
        );
    """)
    
    shared_conn.executemany(
            "INSERT INTO accounting_entries (model, username, datetime, prompt_tokens, completion_tokens, cost, execution_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("gpt-4", "user1", "2024-01-01 10:00", 100, 200, 0.06, 1.5),
                ("gpt-4", "user2", "2024-01-01 11:00", 150, 250, 0.09, 2.1),
                ("gpt-3.5", "user1", "2024-01-01 12:00", 50, 100, 0.002, 0.8),
                ("gpt-3.5", "user3", "2024-01-01 13:00", 75, 150, 0.003, 1.2),
            ]
    )
    return backend
