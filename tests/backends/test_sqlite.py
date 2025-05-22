import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from llm_accounting.backends.base import UsageEntry
from llm_accounting.backends.sqlite import SQLiteBackend

logger = logging.getLogger(__name__)


def test_initialize(sqlite_backend):
    """Test database initialization"""
    # The backend is already initialized by the fixture
    backend = sqlite_backend

    # Verify table exists
    # Access the connection directly for verification purposes in this specific test
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounting_entries'")
        assert cursor.fetchone() is not None

        # Verify columns
        cursor = conn.execute("PRAGMA table_info(accounting_entries)")
        columns = {row[1] for row in cursor.fetchall()}
        required_columns = {
            'id', 'datetime', 'model', 'prompt_tokens', 'completion_tokens',
            'total_tokens', 'local_prompt_tokens', 'local_completion_tokens',
            'local_total_tokens', 'cost', 'execution_time'
        }
        assert required_columns.issubset(columns)


def test_insert_usage(sqlite_backend):
    """Test inserting usage entries"""
    backend = sqlite_backend

    # Create test entry
    entry = UsageEntry(
        model="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.002,
        execution_time=1.5
    )

    # Insert entry
    backend.insert_usage(entry)

    # Verify entry was inserted
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT * FROM accounting_entries")
        row = cursor.fetchone()
        assert row is not None
        assert row[2] == "test-model"  # model column
        assert row[3] == 100  # prompt_tokens
        assert row[4] == 50  # completion_tokens
        assert row[5] == 150  # total_tokens
        assert row[9] == 0.002  # cost
        assert row[10] == 1.5  # execution_time


def test_get_period_stats(sqlite_backend):
    """Test getting period statistics"""
    backend = sqlite_backend

    # Create test entries
    now = datetime.now()
    entries = [
        UsageEntry(
            model="model1",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            timestamp=now - timedelta(hours=2)
        ),
        UsageEntry(
            model="model2",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.001,
            execution_time=0.8,
            timestamp=now - timedelta(hours=1)
        )
    ]

    # Insert entries
    for entry in entries:
        backend.insert_usage(entry)

    # Get stats for the last 3 hours
    end = now
    start = now - timedelta(hours=3)
    stats = backend.get_period_stats(start, end)

    # Verify stats
    assert stats.sum_prompt_tokens == 300  # 100 + 200
    assert stats.sum_completion_tokens == 150  # 50 + 100
    assert stats.sum_total_tokens == 450  # 150 + 300
    assert stats.sum_cost == 0.003  # 0.002 + 0.001
    assert stats.sum_execution_time == 2.3  # 1.5 + 0.8

    # The backend is closed by the fixture teardown


def test_get_model_stats(sqlite_backend):
    """Test getting model-specific statistics"""
    backend = sqlite_backend

    # Create test entries
    now = datetime.now()
    entries = [
        UsageEntry(
            model="model1",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            timestamp=now - timedelta(hours=2)
        ),
        UsageEntry(
            model="model1",
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
            cost=0.003,
            execution_time=2.0,
            timestamp=now - timedelta(hours=1)
        ),
        UsageEntry(
            model="model2",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.001,
            execution_time=0.8,
            timestamp=now
        )
    ]

    # Insert entries
    for entry in entries:
        backend.insert_usage(entry)

    # Get stats for the last 3 hours
    end = now
    start = now - timedelta(hours=3)
    model_stats = backend.get_model_stats(start, end)

    # Convert to dict for easier testing
    stats_by_model = {model: stats for model, stats in model_stats}

    # Verify model1 stats
    model1_stats = stats_by_model["model1"]
    assert model1_stats.sum_prompt_tokens == 250  # 100 + 150
    assert model1_stats.sum_completion_tokens == 125  # 50 + 75
    assert model1_stats.sum_total_tokens == 375  # 150 + 225
    assert model1_stats.sum_cost == 0.005  # 0.002 + 0.003
    assert model1_stats.sum_execution_time == 3.5  # 1.5 + 2.0

    # Verify model2 stats
    model2_stats = stats_by_model["model2"]
    assert model2_stats.sum_prompt_tokens == 200
    assert model2_stats.sum_completion_tokens == 100
    assert model2_stats.sum_total_tokens == 300
    assert model2_stats.sum_cost == 0.001
    assert model2_stats.sum_execution_time == 0.8

    # The backend is closed by the fixture teardown


def test_get_model_rankings(sqlite_backend):
    """Test getting model rankings"""
    backend = sqlite_backend

    # Create test entries
    now = datetime.now()
    entries = [
        UsageEntry(
            model="model1",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            timestamp=now - timedelta(hours=2)
        ),
        UsageEntry(
            model="model1",
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
            cost=0.003,
            execution_time=2.0,
            timestamp=now - timedelta(hours=1)
        ),
        UsageEntry(
            model="model2",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.001,
            execution_time=0.8,
            timestamp=now
        )
    ]

    # Insert entries
    for entry in entries:
        backend.insert_usage(entry)

    # Get rankings for the last 3 hours
    end = now
    start = now - timedelta(hours=3)
    rankings = backend.get_model_rankings(start, end)

    # Verify prompt tokens ranking
    prompt_tokens_ranking = rankings['prompt_tokens']
    assert prompt_tokens_ranking[0][0] == "model1"  # First place
    assert prompt_tokens_ranking[0][1] == 250  # 100 + 150
    assert prompt_tokens_ranking[1][0] == "model2"  # Second place
    assert prompt_tokens_ranking[1][1] == 200

    # Verify cost ranking
    cost_ranking = rankings['cost']
    assert cost_ranking[0][0] == "model1"  # First place
    assert cost_ranking[0][1] == 0.005  # 0.002 + 0.003
    assert cost_ranking[1][0] == "model2"  # Second place
    assert cost_ranking[1][1] == 0.001

    # The backend is closed by the fixture teardown


def test_purge(sqlite_backend):
    """Test purging all entries from the database"""
    backend = sqlite_backend

    # Create and insert test entries
    now = datetime.now()
    entries = [
        UsageEntry(
            model="model1",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            timestamp=now - timedelta(hours=2)
        ),
        UsageEntry(
            model="model2",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.001,
            execution_time=0.8,
            timestamp=now - timedelta(hours=1)
        )
    ]

    # Insert entries
    for entry in entries:
        backend.insert_usage(entry)

    # Verify entries were inserted
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM accounting_entries")
        row = cursor.fetchone()
        count = row[0] if row else 0
        assert count == 2

    # Purge entries
    backend.purge()

    # Verify all entries were deleted
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM accounting_entries")
        row = cursor.fetchone()
        count = row[0] if row else 0
        assert count == 0


def test_purge_empty_database(sqlite_backend):
    """Test purging an empty database"""
    backend = sqlite_backend

    # Verify database is empty
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM accounting_entries")
        row = cursor.fetchone()
        count = row[0] if row else 0
        assert count == 0

    # Purge should not raise any errors
    backend.purge()

    # Verify database is still empty
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM accounting_entries")
        row = cursor.fetchone()
        count = row[0] if row else 0
        assert count == 0
