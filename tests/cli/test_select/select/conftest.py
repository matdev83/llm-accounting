import pytest
from llm_accounting.backends.sqlite import SQLiteBackend
import sqlite3
import typing
from unittest.mock import patch

@pytest.fixture
def test_db():
    """Fixture setting up an in-memory test database with sample data"""
    # Use a unique in-memory database for each test to avoid locking issues
    backend = SQLiteBackend("file::memory:")
    backend.initialize()
    conn = typing.cast(sqlite3.Connection, backend.conn)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounting_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            model TEXT NOT NULL,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            local_prompt_tokens INTEGER,
            local_completion_tokens INTEGER,
            local_total_tokens INTEGER,
            cost REAL NOT NULL,
            execution_time REAL NOT NULL,
            caller_name TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            cached_tokens INTEGER NOT NULL DEFAULT 0,
            reasoning_tokens INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.executemany(
            "INSERT INTO accounting_entries (model, username, datetime, prompt_tokens, completion_tokens, total_tokens, cost, execution_time, cached_tokens, reasoning_tokens) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("gpt-4", "user1", "2024-01-01 10:00", 100, 150, 250, 0.06, 1.5, 0, 0),
                ("gpt-4", "user2", "2024-01-01 11:00", 150, 100, 250, 0.09, 2.1, 0, 0),
                ("gpt-3.5", "user1", "2024-01-01 12:00", 50, 75, 125, 0.002, 0.8, 0, 0),
                ("gpt-3.5", "user3", "2024-01-01 13:00", 75, 50, 125, 0.003, 1.2, 0, 0),
            ]
    )
    conn.commit()
    print(f"Data inserted. Rows in accounting_entries: {conn.execute('SELECT COUNT(*) FROM accounting_entries').fetchone()[0]}")
    return backend

@pytest.fixture(autouse=True)
def mock_get_accounting(test_db):
    """
    Fixture to patch llm_accounting.cli.get_accounting to return our test_db backend.
    This ensures that CLI commands use the in-memory database.
    """
    with patch('llm_accounting.cli.get_accounting') as mock_get_acc:
        # Create a mock LLMAccounting instance that uses our test_db as its backend
        mock_accounting_instance = type('MockLLMAccounting', (object,), {
            'backend': test_db,
            '__enter__': lambda self: self,
            '__exit__': lambda self, exc_type, exc_val, exc_tb: None,
            'get_period_stats': test_db.get_period_stats,
            'get_model_stats': test_db.get_model_stats,
            'get_model_rankings': test_db.get_model_rankings,
            'purge': test_db.purge,
            'tail': test_db.tail,
            'track_usage': test_db.insert_usage, # Assuming track_usage maps to insert_usage for testing
        })()
        mock_get_acc.return_value = mock_accounting_instance
        yield
