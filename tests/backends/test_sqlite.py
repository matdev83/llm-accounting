import logging
import sqlite3
from datetime import datetime, timedelta, timezone # Ensure timezone is imported
from pathlib import Path
from typing import List 

import pytest

from llm_accounting.backends.base import UsageEntry
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import UsageLimitData, LimitScope, LimitType, TimeInterval

logger = logging.getLogger(__name__)


@pytest.fixture
def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)

def test_initialize(sqlite_backend):
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
            'local_total_tokens', 'cost', 'execution_time', 'caller_name', 'username'
        }
        assert required_columns.issubset(columns)

        cursor = conn.execute("PRAGMA table_info(usage_limits)")
        columns = {row[1] for row in cursor.fetchall()}
        required_limit_columns = {
            'id', 'scope', 'limit_type', 'max_value', 'interval_unit', 
            'interval_value', 'model', 'username', 'caller_name', 
            'created_at', 'updated_at'
        }
        assert required_limit_columns.issubset(columns)


def test_insert_usage(sqlite_backend):
    backend = sqlite_backend
    entry = UsageEntry(
        model="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.002,
        execution_time=1.5
    )
    backend.insert_usage(entry)
    with sqlite3.connect(backend.db_path) as conn:
        cursor = conn.execute("SELECT * FROM accounting_entries")
        row = cursor.fetchone()
        assert row is not None
        assert row[2] == "test-model"
        assert row[3] == 100


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
    backend.insert_usage_limit(UsageLimitData(scope=LimitScope.GLOBAL.value, limit_type=LimitType.COST.value, max_value=100, interval_unit=TimeInterval.MONTH.value, interval_value=1))

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


def test_insert_and_get_usage_limits(sqlite_backend: SQLiteBackend, now_utc: datetime):
    limit1_created_at = (now_utc - timedelta(days=1)).replace(tzinfo=None) 
    limit1_updated_at = (now_utc - timedelta(hours=12)).replace(tzinfo=None)
    
    limit_to_insert1 = UsageLimitData(
        scope=LimitScope.USER.value,
        limit_type=LimitType.COST.value,
        max_value=100.0,
        interval_unit=TimeInterval.MONTH.value,
        interval_value=1,
        username="test_user_1",
        created_at=limit1_created_at,
        updated_at=limit1_updated_at
    )
    sqlite_backend.insert_usage_limit(limit_to_insert1)

    limit2_created_at = (now_utc - timedelta(days=2)).replace(tzinfo=None)
    limit2_updated_at = (now_utc - timedelta(days=1)).replace(tzinfo=None)
    limit_to_insert2 = UsageLimitData(
        scope=LimitScope.MODEL.value,
        limit_type=LimitType.REQUESTS.value,
        max_value=1000.0,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
        model="gpt-4-turbo",
        created_at=limit2_created_at,
        updated_at=limit2_updated_at
    )
    sqlite_backend.insert_usage_limit(limit_to_insert2)

    retrieved_limits: List[UsageLimitData] = sqlite_backend.get_usage_limits()
    assert len(retrieved_limits) == 2

    found_limit1 = False
    found_limit2 = False

    for limit_obj in retrieved_limits: # Renamed limit to limit_obj to avoid conflict
        assert isinstance(limit_obj, UsageLimitData)
        assert limit_obj.id is not None 
        
        assert isinstance(limit_obj.created_at, datetime)
        assert isinstance(limit_obj.updated_at, datetime)
        assert limit_obj.created_at.tzinfo == timezone.utc # Now expecting UTC aware
        assert limit_obj.updated_at.tzinfo == timezone.utc # Now expecting UTC aware

        if limit_obj.username == "test_user_1":
            found_limit1 = True
            assert limit_obj.scope == limit_to_insert1.scope
            assert limit_obj.limit_type == limit_to_insert1.limit_type
            assert limit_obj.max_value == limit_to_insert1.max_value
            assert limit_obj.interval_unit == limit_to_insert1.interval_unit
            assert limit_obj.interval_value == limit_to_insert1.interval_value
            # Compare aware datetime with aware datetime
            assert limit_obj.created_at == limit1_created_at.replace(tzinfo=timezone.utc)
            assert limit_obj.updated_at == limit1_updated_at.replace(tzinfo=timezone.utc)
        elif limit_obj.model == "gpt-4-turbo":
            found_limit2 = True
            assert limit_obj.scope == limit_to_insert2.scope
            assert limit_obj.limit_type == limit_to_insert2.limit_type
            assert limit_obj.created_at == limit2_created_at.replace(tzinfo=timezone.utc)
            assert limit_obj.updated_at == limit2_updated_at.replace(tzinfo=timezone.utc)
            
    assert found_limit1
    assert found_limit2

def test_get_usage_limits_with_filters(sqlite_backend: SQLiteBackend, now_utc: datetime):
    dt_naive = now_utc.replace(tzinfo=None) # For insertion
    dt_aware = now_utc # For comparison after retrieval

    limit1 = UsageLimitData(scope=LimitScope.USER.value, limit_type=LimitType.COST.value, max_value=100, interval_unit="month", interval_value=1, username="user1", created_at=dt_naive, updated_at=dt_naive)
    limit2 = UsageLimitData(scope=LimitScope.MODEL.value, limit_type=LimitType.REQUESTS.value, max_value=1000, interval_unit="day", interval_value=1, model="modelA", created_at=dt_naive, updated_at=dt_naive)
    limit3 = UsageLimitData(scope=LimitScope.USER.value, limit_type=LimitType.COST.value, max_value=200, interval_unit="month", interval_value=1, username="user2", model="modelA", created_at=dt_naive, updated_at=dt_naive)
    
    sqlite_backend.insert_usage_limit(limit1)
    sqlite_backend.insert_usage_limit(limit2)
    sqlite_backend.insert_usage_limit(limit3)

    user_limits = sqlite_backend.get_usage_limits(scope=LimitScope.USER)
    assert len(user_limits) == 2
    assert all(l.scope == LimitScope.USER.value for l in user_limits)

    model_a_limits = sqlite_backend.get_usage_limits(model="modelA")
    assert len(model_a_limits) == 2 
    assert all(l.model == "modelA" for l in model_a_limits)

    user1_limits = sqlite_backend.get_usage_limits(username="user1")
    assert len(user1_limits) == 1
    assert user1_limits[0].username == "user1"

    user_model_limits = sqlite_backend.get_usage_limits(scope=LimitScope.USER, model="modelA")
    assert len(user_model_limits) == 1
    assert user_model_limits[0].username == "user2" 
    assert user_model_limits[0].model == "modelA"


def test_delete_usage_limit(sqlite_backend: SQLiteBackend, now_utc: datetime):
    dt_naive = now_utc.replace(tzinfo=None)
    limit_to_delete_spec = UsageLimitData(
        scope=LimitScope.GLOBAL.value,
        limit_type=LimitType.COST.value,
        max_value=50.0,
        interval_unit=TimeInterval.WEEK.value,
        interval_value=1,
        caller_name="test_caller_delete",
        created_at=dt_naive,
        updated_at=dt_naive
    )
    sqlite_backend.insert_usage_limit(limit_to_delete_spec)

    all_limits = sqlite_backend.get_usage_limits(caller_name="test_caller_delete")
    assert len(all_limits) == 1
    limit_id_to_delete = all_limits[0].id
    assert limit_id_to_delete is not None

    sqlite_backend.delete_usage_limit(limit_id_to_delete)

    remaining_limits = sqlite_backend.get_usage_limits(caller_name="test_caller_delete")
    assert len(remaining_limits) == 0

    try:
        sqlite_backend.delete_usage_limit(99999) 
    except Exception as e:
        pytest.fail(f"Deleting a non-existent limit raised an exception: {e}")

def test_datetime_precision_and_timezone_handling(sqlite_backend: SQLiteBackend):
    aware_dt = datetime.now(timezone.utc).replace(microsecond=123456)
    limit_aware = UsageLimitData(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.COST.value, max_value=1, interval_unit="day", interval_value=1,
        created_at=aware_dt, updated_at=aware_dt
    )
    sqlite_backend.insert_usage_limit(limit_aware)
    
    retrieved_aware_list = sqlite_backend.get_usage_limits(scope=LimitScope.GLOBAL)
    assert len(retrieved_aware_list) >= 1 
    
    retrieved_aware = None
    for l_aware in retrieved_aware_list:
        if l_aware.created_at and l_aware.created_at == aware_dt: # Direct comparison for aware datetimes
             retrieved_aware = l_aware
             break
    assert retrieved_aware is not None, "Inserted aware_dt limit not found"
    
    assert retrieved_aware.created_at.tzinfo == timezone.utc # Check it's aware
    assert retrieved_aware.created_at.year == aware_dt.year
    assert retrieved_aware.created_at.month == aware_dt.month
    assert retrieved_aware.created_at.day == aware_dt.day
    assert retrieved_aware.created_at.hour == aware_dt.hour
    assert retrieved_aware.created_at.minute == aware_dt.minute
    assert retrieved_aware.created_at.second == aware_dt.second
    assert retrieved_aware.created_at.microsecond == aware_dt.microsecond
    assert retrieved_aware.created_at.utcoffset() == timedelta(0)

    # Test with naive datetime (conventionally UTC)
    naive_dt = datetime.now(timezone.utc).replace(microsecond=654321)
    limit_naive = UsageLimitData(
        scope=LimitScope.USER.value, limit_type=LimitType.REQUESTS.value, max_value=1, interval_unit="hour", interval_value=1, username="naive_user",
        created_at=naive_dt, updated_at=naive_dt # Inserted as naive
    )
    sqlite_backend.insert_usage_limit(limit_naive)
    retrieved_naive_list = sqlite_backend.get_usage_limits(scope=LimitScope.USER, username="naive_user")
    assert len(retrieved_naive_list) == 1
    retrieved_naive_obj = retrieved_naive_list[0]

    # Expect retrieved datetime to be UTC-aware
    assert retrieved_naive_obj.created_at.tzinfo == timezone.utc 
    # Compare by making the original naive_dt UTC-aware
    assert retrieved_naive_obj.created_at == naive_dt.replace(tzinfo=timezone.utc)
    assert retrieved_naive_obj.updated_at.tzinfo == timezone.utc
    assert retrieved_naive_obj.updated_at == naive_dt.replace(tzinfo=timezone.utc)


    # Test with None datetimes (should use DB defaults and be retrieved as UTC-aware)
    limit_none_dt = UsageLimitData(
        scope=LimitScope.CALLER.value, limit_type=LimitType.REQUESTS.value, max_value=10000, interval_unit="week", interval_value=1, caller_name="none_dt_caller",
        created_at=None, updated_at=None
    )
    sqlite_backend.insert_usage_limit(limit_none_dt)
    retrieved_none_dt_list = sqlite_backend.get_usage_limits(scope=LimitScope.CALLER, caller_name="none_dt_caller")
    assert len(retrieved_none_dt_list) == 1
    retrieved_none_dt = retrieved_none_dt_list[0]
    
    assert isinstance(retrieved_none_dt.created_at, datetime)
    assert retrieved_none_dt.created_at.tzinfo == timezone.utc # Expect UTC aware from DB default
    assert isinstance(retrieved_none_dt.updated_at, datetime)
    assert retrieved_none_dt.updated_at.tzinfo == timezone.utc # Expect UTC aware from DB default
    
    current_utc_aware = datetime.now(timezone.utc)
    assert (current_utc_aware - retrieved_none_dt.created_at).total_seconds() < 10 
    assert (current_utc_aware - retrieved_none_dt.updated_at).total_seconds() < 10
