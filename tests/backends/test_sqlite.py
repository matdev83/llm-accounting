import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from llm_accounting.backends.base import UsageEntry
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import UsageLimit, LimitScope, LimitType, TimeInterval


logger = logging.getLogger(__name__)


def test_initialize(sqlite_backend):
    """Test database initialization"""
    backend = sqlite_backend
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounting_entries'")
        assert cursor.fetchone() is not None
        cursor = conn.execute("PRAGMA table_info(accounting_entries)")
        columns = {row[1] for row in cursor.fetchall()}
        required_columns = {
            'id', 'timestamp', 'model', 'prompt_tokens', 'completion_tokens',
            'total_tokens', 'local_prompt_tokens', 'local_completion_tokens',
            'local_total_tokens', 'cost', 'execution_time', 'project'
        }
        assert required_columns.issubset(columns)

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usage_limits'")
        assert cursor.fetchone() is not None
        cursor = conn.execute("PRAGMA table_info(usage_limits)")
        columns = {row[1] for row in cursor.fetchall()}
        required_limit_columns = {
            'id', 'scope', 'limit_type', 'model', 'username', 
            'caller_name', 'project_name', 'max_value', 
            'interval_unit', 'interval_value', 'created_at', 'updated_at'
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

# --- Tests for Project-based Limits ---

def test_insert_project_scope_limit(sqlite_backend: SQLiteBackend):
    """Test inserting a usage limit with PROJECT scope."""
    project_name = "Solaris"
    limit = UsageLimit(
        scope=LimitScope.PROJECT,
        limit_type=LimitType.COST,
        max_value=100.0,
        interval_unit=TimeInterval.MONTH,
        interval_value=1,
        project_name=project_name
    )
    sqlite_backend.insert_usage_limit(limit)
    
    retrieved_limits = sqlite_backend.get_usage_limits(scope=LimitScope.PROJECT, project_name=project_name)
    assert len(retrieved_limits) == 1
    retrieved_limit = retrieved_limits[0]
    assert retrieved_limit.scope == LimitScope.PROJECT.value
    assert retrieved_limit.project_name == project_name
    assert retrieved_limit.max_value == 100.0

def test_get_usage_limits_filter_by_project_scope(sqlite_backend: SQLiteBackend):
    """Test filtering limits by PROJECT scope."""
    sqlite_backend.insert_usage_limit(UsageLimit(LimitScope.GLOBAL, LimitType.COST, 1000, TimeInterval.MONTH, 1))
    sqlite_backend.insert_usage_limit(UsageLimit(LimitScope.PROJECT, LimitType.REQUESTS, 500, TimeInterval.DAY, 1, project_name="ProjectX"))
    sqlite_backend.insert_usage_limit(UsageLimit(LimitScope.PROJECT, LimitType.COST, 200, TimeInterval.WEEK, 1, project_name="ProjectY"))
    
    project_limits = sqlite_backend.get_usage_limits(scope=LimitScope.PROJECT)
    assert len(project_limits) == 2
    assert all(limit.scope == LimitScope.PROJECT.value for limit in project_limits)
    
    project_x_limits = sqlite_backend.get_usage_limits(scope=LimitScope.PROJECT, project_name="ProjectX")
    assert len(project_x_limits) == 1
    assert project_x_limits[0].project_name == "ProjectX"
    assert project_x_limits[0].limit_type == LimitType.REQUESTS.value

def test_get_accounting_entries_for_quota_with_project_filter(sqlite_backend: SQLiteBackend):
    """Test get_accounting_entries_for_quota filtering by project_name."""
    now = datetime.now(timezone.utc)
    project_one = "ProjectOne"
    project_two = "ProjectTwo"

    # Entries for ProjectOne
    sqlite_backend.insert_usage(UsageEntry(model="gpt-4", cost=1.0, execution_time=1, project=project_one, timestamp=now - timedelta(minutes=10)))
    sqlite_backend.insert_usage(UsageEntry(model="gpt-4", cost=1.5, execution_time=1, project=project_one, timestamp=now - timedelta(minutes=5)))
    
    # Entries for ProjectTwo
    sqlite_backend.insert_usage(UsageEntry(model="gpt-4", cost=2.0, execution_time=1, project=project_two, timestamp=now - timedelta(minutes=10)))
    
    # Entry with no project
    sqlite_backend.insert_usage(UsageEntry(model="gpt-4", cost=0.5, execution_time=1, timestamp=now - timedelta(minutes=5))) # No project

    start_time = now - timedelta(hours=1)
    
    # Quota for ProjectOne
    cost_project_one = sqlite_backend.get_accounting_entries_for_quota(
        start_time=start_time, limit_type=LimitType.COST, project_name=project_one
    )
    assert cost_project_one == 2.5 # 1.0 + 1.5

    # Quota for ProjectTwo
    cost_project_two = sqlite_backend.get_accounting_entries_for_quota(
        start_time=start_time, limit_type=LimitType.COST, project_name=project_two
    )
    assert cost_project_two == 2.0

    # Quota for entries with NO project (project_name=None)
    cost_no_project = sqlite_backend.get_accounting_entries_for_quota(
        start_time=start_time, limit_type=LimitType.COST, project_name=None 
    )
    # This should sum all entries if project_name is None and the backend logic for get_accounting_entries_for_quota
    # does not add "AND project IS NULL" when project_name is None.
    # Current backend logic: if project_name is provided, filter by it. If None, no project filter.
    # So, this will sum all projects.
    # To test summing for "IS NULL", the parameter might need a sentinel or specific handling.
    # The current implementation of get_accounting_entries_for_quota in sqlite.py:
    # if project_name: query += " AND project = ?"; params.append(project_name)
    # else: # project_name is None -> no additional project filter, so sums all.
    # This assertion reflects that.
    assert cost_no_project == 5.0 # 1.0 + 1.5 + 2.0 + 0.5

    # If we want to test sum for only entries where project IS NULL, we'd need a different call or modified backend logic.
    # E.g., a dedicated parameter or a sentinel value for project_name.
    # For now, this confirms project_name=None means "no project filter".

# --- Existing Tests (abbreviated for brevity) ---
def test_get_period_stats(sqlite_backend):
    backend = sqlite_backend; now = datetime.now()
    entries = [UsageEntry(model="model1",cost=0.002,execution_time=1.5,timestamp=now - timedelta(hours=2)), UsageEntry(model="model2",cost=0.001,execution_time=0.8,timestamp=now - timedelta(hours=1))]
    for entry in entries: backend.insert_usage(entry)
    stats = backend.get_period_stats(now - timedelta(hours=3), now)
    assert stats.sum_cost == 0.003

def test_get_model_stats(sqlite_backend):
    backend = sqlite_backend; now = datetime.now()
    entries = [UsageEntry(model="model1",cost=0.002,timestamp=now - timedelta(hours=2)), UsageEntry(model="model1",cost=0.003,timestamp=now - timedelta(hours=1)), UsageEntry(model="model2",cost=0.001,timestamp=now)]
    for entry in entries: backend.insert_usage(entry)
    model_stats = backend.get_model_stats(now - timedelta(hours=3), now)
    stats_by_model = {model: stats for model, stats in model_stats}
    assert stats_by_model["model1"].sum_cost == 0.005
    assert stats_by_model["model2"].sum_cost == 0.001

def test_get_model_rankings(sqlite_backend):
    backend = sqlite_backend; now = datetime.now()
    entries = [UsageEntry(model="model1",cost=0.002,timestamp=now - timedelta(hours=2)), UsageEntry(model="model1",cost=0.003,timestamp=now - timedelta(hours=1)), UsageEntry(model="model2",cost=0.001,timestamp=now)]
    for entry in entries: backend.insert_usage(entry)
    rankings = backend.get_model_rankings(now - timedelta(hours=3), now)
    assert rankings['cost'][0][0] == "model1" and rankings['cost'][0][1] == 0.005

def test_purge(sqlite_backend):
    backend = sqlite_backend; backend.insert_usage(UsageEntry(model="model1",cost=0.002))
    with sqlite3.connect(backend.db_path) as conn: assert conn.execute("SELECT COUNT(*) FROM accounting_entries").fetchone()[0] == 1
    backend.purge()
    with sqlite3.connect(backend.db_path) as conn: assert conn.execute("SELECT COUNT(*) FROM accounting_entries").fetchone()[0] == 0
    with sqlite3.connect(backend.db_path) as conn: assert conn.execute("SELECT COUNT(*) FROM usage_limits").fetchone()[0] == 0


def test_purge_empty_database(sqlite_backend):
    backend = sqlite_backend
    backend.purge() # Should not raise errors
    with sqlite3.connect(backend.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounting_entries").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM usage_limits").fetchone()[0] == 0
