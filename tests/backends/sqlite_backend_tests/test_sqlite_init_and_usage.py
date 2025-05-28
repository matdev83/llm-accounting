import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from llm_accounting.backends.base import UsageEntry
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval

def test_initialize(sqlite_backend):
    """Test database initialization"""
    backend = sqlite_backend
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounting_entries'")
        assert cursor.fetchone() is not None
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usage_limits'")
        assert cursor.fetchone() is not None

        cursor = conn.execute("PRAGMA table_info(accounting_entries)")
        columns = {row[1] for row in cursor.fetchall()}
        required_columns = {
            'id', 'timestamp', 'model', 'prompt_tokens', 'completion_tokens',
            'total_tokens', 'local_prompt_tokens', 'local_completion_tokens',
            'local_total_tokens', 'cost', 'execution_time', 'caller_name', 'username', 'project'
        }
        assert required_columns.issubset(columns)

        cursor = conn.execute("PRAGMA table_info(usage_limits)")
        columns = {row[1] for row in cursor.fetchall()}
        required_limit_columns = {
            'id', 'scope', 'limit_type', 'max_value', 'interval_unit',
            'interval_value', 'model', 'username', 'caller_name', 'project_name',
            'created_at', 'updated_at'
        }
        assert required_limit_columns.issubset(columns)


def test_insert_usage(sqlite_backend):
    """Test inserting usage entries"""
    backend = sqlite_backend
    entry = UsageEntry(
        model="test-model", prompt_tokens=100, completion_tokens=50, total_tokens=150,
        cost=0.002, execution_time=1.5
    )
    backend.insert_usage(entry)
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT * FROM accounting_entries")
        row = cursor.fetchone()
        assert row is not None
        assert row[2] == "test-model"
        assert row[3] == 100
        assert row[9] is None
        assert row[10] == 0.002

def test_insert_usage_with_project(sqlite_backend):
    """Test inserting usage entries with a project name."""
    backend = sqlite_backend
    project_name = "TestProjectX"
    entry_with_project = UsageEntry(
        model="test-model-project", cost=0.0025, execution_time=1.8, project=project_name
    )
    backend.insert_usage(entry_with_project)
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT project FROM accounting_entries WHERE model=?", ("test-model-project",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == project_name

def test_tail_retrieves_project(sqlite_backend):
    """Test that tail retrieves the project field correctly."""
    backend = sqlite_backend
    project_name = "TailTestProject"
    entry1 = UsageEntry(model="tail-model-1", cost=0.1, execution_time=1, project=project_name)
    entry2 = UsageEntry(model="tail-model-2", cost=0.2, execution_time=2)
    backend.insert_usage(entry1)
    backend.insert_usage(entry2)
    tailed_entries = backend.tail(n=2)
    assert len(tailed_entries) == 2
    tailed_entry_with_project = next((e for e in tailed_entries if e.model == "tail-model-1"), None)
    tailed_entry_without_project = next((e for e in tailed_entries if e.model == "tail-model-2"), None)
    assert tailed_entry_with_project is not None and tailed_entry_with_project.project == project_name
    assert tailed_entry_without_project is not None and tailed_entry_without_project.project is None

def test_execute_query_filter_by_project(sqlite_backend):
    """Test filtering by project name using execute_query."""
    backend = sqlite_backend
    project_alpha = "ProjectAlpha"
    project_beta = "ProjectBeta"
    backend.insert_usage(UsageEntry(model="modelA", cost=0.1, execution_time=1, project=project_alpha))
    backend.insert_usage(UsageEntry(model="modelB", cost=0.2, execution_time=1, project=project_beta))
    backend.insert_usage(UsageEntry(model="modelC", cost=0.3, execution_time=1, project=project_alpha))
    backend.insert_usage(UsageEntry(model="modelD", cost=0.4, execution_time=1))
    results_alpha = backend.execute_query(f"SELECT model, project FROM accounting_entries WHERE project = '{project_alpha}' ORDER BY model")
    assert len(results_alpha) == 2
    assert results_alpha[0]['project'] == project_alpha
    results_null = backend.execute_query("SELECT model, project FROM accounting_entries WHERE project IS NULL")
    assert len(results_null) == 1
    assert results_null[0]['project'] is None
