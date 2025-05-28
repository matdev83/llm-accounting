import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from llm_accounting.backends.base import UsageEntry
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import UsageLimitDTO, LimitScope, LimitType, TimeInterval

def test_get_period_stats(sqlite_backend, now_utc):
    backend = sqlite_backend
    entries = [
        UsageEntry(
            model="model1", prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.002, execution_time=1.5, timestamp=now_utc - timedelta(hours=2)
        ),
        UsageEntry(
            model="model2", prompt_tokens=200, completion_tokens=100, total_tokens=300,
            cost=0.001, execution_time=0.8, timestamp=now_utc - timedelta(hours=1)
        )
    ]
    for entry in entries:
        backend.insert_usage(entry)
    
    end = now_utc
    start = now_utc - timedelta(hours=3)
    stats = backend.get_period_stats(start, end)

    assert stats.sum_prompt_tokens == 300
    assert stats.sum_completion_tokens == 150
    assert stats.sum_total_tokens == 450
    assert stats.sum_cost == 0.003
    assert stats.sum_execution_time == 2.3


def test_get_model_stats(sqlite_backend, now_utc):
    backend = sqlite_backend
    entries = [
        UsageEntry(model="model1", prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.002, execution_time=1.5, timestamp=now_utc - timedelta(hours=2)),
        UsageEntry(model="model1", prompt_tokens=150, completion_tokens=75, total_tokens=225, cost=0.003, execution_time=2.0, timestamp=now_utc - timedelta(hours=1)),
        UsageEntry(model="model2", prompt_tokens=200, completion_tokens=100, total_tokens=300, cost=0.001, execution_time=0.8, timestamp=now_utc)
    ]
    for entry in entries:
        backend.insert_usage(entry)

    end = now_utc
    start = now_utc - timedelta(hours=3)
    model_stats = backend.get_model_stats(start, end)
    stats_by_model = {model: stats for model, stats in model_stats}

    assert stats_by_model["model1"].sum_prompt_tokens == 250
    assert stats_by_model["model1"].sum_cost == 0.005
    assert stats_by_model["model2"].sum_prompt_tokens == 200
    assert stats_by_model["model2"].sum_cost == 0.001


def test_get_model_rankings(sqlite_backend, now_utc):
    backend = sqlite_backend
    entries = [
        UsageEntry(model="model1", prompt_tokens=100, cost=0.002, timestamp=now_utc - timedelta(hours=2)),
        UsageEntry(model="model1", prompt_tokens=150, cost=0.003, timestamp=now_utc - timedelta(hours=1)),
        UsageEntry(model="model2", prompt_tokens=200, cost=0.001, timestamp=now_utc)
    ]
    for entry in entries:
        backend.insert_usage(entry)

    end = now_utc
    start = now_utc - timedelta(hours=3)
    rankings = backend.get_model_rankings(start, end)

    assert rankings['prompt_tokens'][0] == ("model1", 250)
    assert rankings['prompt_tokens'][1] == ("model2", 200)
    assert rankings['cost'][0] == ("model1", 0.005)
    assert rankings['cost'][1] == ("model2", 0.001)


def test_purge(sqlite_backend):
    backend = sqlite_backend
    backend.insert_usage(UsageEntry(model="model1", prompt_tokens=100, cost=0.002, timestamp=datetime.now(timezone.utc)))
    backend.insert_usage_limit(UsageLimitDTO(scope=LimitScope.GLOBAL.value, limit_type=LimitType.COST.value, max_value=100, interval_unit=TimeInterval.MONTH.value, interval_value=1))

    with sqlite3.connect(backend.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounting_entries").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM usage_limits").fetchone()[0] == 1

    backend.purge()

    with sqlite3.connect(backend.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounting_entries").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM usage_limits").fetchone()[0] == 0


def test_purge_empty_database(sqlite_backend):
    backend = sqlite_backend
    backend.purge()
    with sqlite3.connect(backend.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM accounting_entries").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM usage_limits").fetchone()[0] == 0
