import sqlite3
import typing
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from llm_accounting.backends.sqlite import SQLiteBackend


@pytest.fixture
def test_db():
    """Fixture setting up an in-memory test database with sample data using SQLAlchemy connection."""
    backend = SQLiteBackend(":memory:")
    backend.initialize()
    
    conn = backend.connection_manager.get_connection()
    assert conn is not None, "SQLAlchemy connection not initialized in SQLiteBackend"

    create_table_sql_script = """
        CREATE TABLE IF NOT EXISTS accounting_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
    """
    conn.execute(text(create_table_sql_script))

    insert_sql_template = text("""
        INSERT INTO accounting_entries 
        (model, username, timestamp, prompt_tokens, completion_tokens, total_tokens, cost, execution_time, cached_tokens, reasoning_tokens) 
        VALUES (:model, :username, :timestamp, :prompt_tokens, :completion_tokens, :total_tokens, :cost, :execution_time, :cached_tokens, :reasoning_tokens)
    """)
    
    data_to_insert = [
        {"model": "gpt-4", "username": "user1", "timestamp": "2024-01-01 10:00", "prompt_tokens": 100, "completion_tokens": 150, "total_tokens": 250, "cost": 0.06, "execution_time": 1.5, "cached_tokens": 0, "reasoning_tokens": 0},
        {"model": "gpt-4", "username": "user2", "timestamp": "2024-01-01 11:00", "prompt_tokens": 150, "completion_tokens": 100, "total_tokens": 250, "cost": 0.09, "execution_time": 2.1, "cached_tokens": 0, "reasoning_tokens": 0},
        {"model": "gpt-3.5", "username": "user1", "timestamp": "2024-01-01 12:00", "prompt_tokens": 50, "completion_tokens": 75, "total_tokens": 125, "cost": 0.002, "execution_time": 0.8, "cached_tokens": 0, "reasoning_tokens": 0},
        {"model": "gpt-3.5", "username": "user3", "timestamp": "2024-01-01 13:00", "prompt_tokens": 75, "completion_tokens": 50, "total_tokens": 125, "cost": 0.003, "execution_time": 1.2, "cached_tokens": 0, "reasoning_tokens": 0},
    ]
    
    conn.execute(insert_sql_template, data_to_insert)
    conn.commit()

    count_result = conn.execute(text('SELECT COUNT(*) FROM accounting_entries')).scalar_one()
    print(f"Data inserted. Rows in accounting_entries: {count_result}")
    return backend


@pytest.fixture # Removed autouse=True
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
        mock_accounting_instance.__exit__.return_value = None

        mock_accounting_instance.get_period_stats.side_effect = test_db.get_period_stats
        mock_accounting_instance.get_model_stats.side_effect = test_db.get_model_stats
        mock_accounting_instance.get_model_rankings.side_effect = test_db.get_model_rankings
        mock_accounting_instance.purge.side_effect = test_db.purge
        mock_accounting_instance.tail.side_effect = test_db.tail
        mock_accounting_instance.track_usage.side_effect = test_db.insert_usage

        mock_get_acc.return_value = mock_accounting_instance
        yield mock_get_acc
