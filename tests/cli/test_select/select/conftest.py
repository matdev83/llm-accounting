import sqlite3
import typing
from unittest.mock import MagicMock, patch

import pytest

from llm_accounting.backends.sqlite import SQLiteBackend


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
    Fixture to patch llm_accounting.cli.get_accounting to return a mock LLMAccounting
    instance that uses our test_db backend. This ensures that CLI commands use the
    in-memory database and that mock calls are properly tracked.
    """
    with patch('llm_accounting.cli.utils.get_accounting') as mock_get_acc:
        mock_accounting_instance = MagicMock()
        mock_accounting_instance.backend = test_db
        mock_accounting_instance.__enter__.return_value = mock_accounting_instance
        mock_accounting_instance.__exit__.return_value = None  # Ensure __exit__ is callable and returns None

        # Explicitly mock methods that are called on the LLMAccounting instance
        # and delegate them to the test_db backend
        mock_accounting_instance.get_period_stats.side_effect = test_db.get_period_stats
        mock_accounting_instance.get_model_stats.side_effect = test_db.get_model_stats
        mock_accounting_instance.get_model_rankings.side_effect = test_db.get_model_rankings
        mock_accounting_instance.purge.side_effect = test_db.purge
        mock_accounting_instance.tail.side_effect = test_db.tail
        mock_accounting_instance.track_usage.side_effect = test_db.insert_usage  # LLMAccounting.track_usage calls backend.insert_usage

        mock_get_acc.return_value = mock_accounting_instance
        yield mock_get_acc  # Yield the mock object for further assertions in tests
