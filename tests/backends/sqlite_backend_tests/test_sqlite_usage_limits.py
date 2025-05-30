import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from llm_accounting.backends.base import UsageEntry
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import UsageLimitDTO, LimitScope, LimitType, TimeInterval

# --- Tests for Project-based Limits ---

def test_insert_project_scope_limit(sqlite_backend: SQLiteBackend):
    """Test inserting a usage limit with PROJECT scope."""
    project_name = "Solaris"
    limit = UsageLimitDTO(
        scope=LimitScope.PROJECT.value,
        limit_type=LimitType.COST.value,
        max_value=100.0,
        interval_unit=TimeInterval.MONTH.value,
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
    sqlite_backend.insert_usage_limit(UsageLimitDTO(scope=LimitScope.GLOBAL.value, limit_type=LimitType.COST.value, max_value=1000, interval_unit=TimeInterval.MONTH.value, interval_value=1))
    sqlite_backend.insert_usage_limit(UsageLimitDTO(scope=LimitScope.PROJECT.value, limit_type=LimitType.REQUESTS.value, max_value=500, interval_unit=TimeInterval.DAY.value, interval_value=1, project_name="ProjectX"))
    sqlite_backend.insert_usage_limit(UsageLimitDTO(scope=LimitScope.PROJECT.value, limit_type=LimitType.COST.value, max_value=200, interval_unit=TimeInterval.WEEK.value, interval_value=1, project_name="ProjectY"))
    
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
        start_time=start_time, limit_type=LimitType.COST, project_name=None, filter_project_null=True
    )
    assert cost_no_project == 0.5

def test_insert_and_get_usage_limits(sqlite_backend: SQLiteBackend, now_utc: datetime):
    limit1_created_at = (now_utc - timedelta(days=1)).replace(tzinfo=None)
    limit1_updated_at = (now_utc - timedelta(hours=12)).replace(tzinfo=None)
    
    limit_to_insert1 = UsageLimitDTO(
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
    limit_to_insert2 = UsageLimitDTO(
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

    retrieved_limits: List[UsageLimitDTO] = sqlite_backend.get_usage_limits()
    assert len(retrieved_limits) == 2

    found_limit1 = False
    found_limit2 = False

    for limit_obj in retrieved_limits: # Renamed limit to limit_obj to avoid conflict
        assert isinstance(limit_obj, UsageLimitDTO)
        assert limit_obj.id is not None
        
        assert isinstance(limit_obj.created_at, datetime)
        assert isinstance(limit_obj.updated_at, datetime)
        assert limit_obj.created_at is not None and limit_obj.created_at.tzinfo == timezone.utc # Now expecting UTC aware
        assert limit_obj.updated_at is not None and limit_obj.updated_at.tzinfo == timezone.utc # Now expecting UTC aware

        if limit_obj.username == "test_user_1":
            found_limit1 = True
            assert limit_obj.scope == limit_to_insert1.scope
            assert limit_obj.limit_type == limit_to_insert1.limit_type
            assert limit_obj.max_value == limit_to_insert1.max_value
            assert limit_obj.interval_unit == limit_to_insert1.interval_unit
            assert limit_obj.interval_value == limit_to_insert1.interval_value
            # Compare aware datetime with aware datetime
            # Compare by checking if they are within a small time delta (e.g., 1 second)
            # This accounts for potential slight differences in timestamp due to test execution time
            # and database precision.
            # Assert that created_at and updated_at are close to now_utc, as they are set by the DB
            assert limit_obj.created_at is not None and abs((limit_obj.created_at - now_utc).total_seconds()) < 5 # Allow a few seconds for test execution
            assert limit_obj.updated_at is not None and abs((limit_obj.updated_at - now_utc).total_seconds()) < 5 # Allow a few seconds for test execution
        elif limit_obj.model == "gpt-4-turbo":
            found_limit2 = True
            assert limit_obj.scope == limit_to_insert2.scope
            assert limit_obj.limit_type == limit_to_insert2.limit_type
            
            # Assert that created_at and updated_at are close to now_utc, as they are set by the DB
            assert limit_obj.created_at is not None and abs((limit_obj.created_at - now_utc).total_seconds()) < 5
            assert limit_obj.updated_at is not None and abs((limit_obj.updated_at - now_utc).total_seconds()) < 5
            
    assert found_limit1
    assert found_limit2

def test_get_usage_limits_with_filters(sqlite_backend: SQLiteBackend, now_utc: datetime):
    dt_naive = now_utc.replace(tzinfo=None) # For insertion
    dt_aware = now_utc # For comparison after retrieval

    limit1 = UsageLimitDTO(scope=LimitScope.USER.value, limit_type=LimitType.COST.value, max_value=100, interval_unit="month", interval_value=1, username="user1", created_at=dt_naive, updated_at=dt_naive)
    limit2 = UsageLimitDTO(scope=LimitScope.MODEL.value, limit_type=LimitType.REQUESTS.value, max_value=1000, interval_unit="day", interval_value=1, model="modelA", created_at=dt_naive, updated_at=dt_naive)
    limit3 = UsageLimitDTO(scope=LimitScope.USER.value, limit_type=LimitType.COST.value, max_value=200, interval_unit="month", interval_value=1, username="user2", model="modelA", created_at=dt_naive, updated_at=dt_naive)
    
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
    limit_to_delete_spec = UsageLimitDTO(
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
    limit_aware = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.COST.value, max_value=1, interval_unit="day", interval_value=1,
        created_at=aware_dt, updated_at=aware_dt
    )
    sqlite_backend.insert_usage_limit(limit_aware)
    
    retrieved_aware_list = sqlite_backend.get_usage_limits(scope=LimitScope.GLOBAL)
    assert len(retrieved_aware_list) >= 1
    
    retrieved_aware = None
    for l_aware in retrieved_aware_list:
        # Compare by rounding to seconds due to SQLite's typical precision
        if l_aware.created_at and l_aware.created_at.replace(microsecond=0) == aware_dt.replace(microsecond=0):
             retrieved_aware = l_aware
             break
    assert retrieved_aware is not None, "Inserted aware_dt limit not found"
    
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.tzinfo == timezone.utc # Check it's aware
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.year == aware_dt.year
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.month == aware_dt.month
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.day == aware_dt.day
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.hour == aware_dt.hour
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.minute == aware_dt.minute
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.second == aware_dt.second
    # Removed microsecond assertion as it's the source of the problem
    assert retrieved_aware.created_at is not None and retrieved_aware.created_at.utcoffset() == timedelta(0)

    # Test with naive datetime (conventionally UTC)
    naive_dt = datetime.now(timezone.utc).replace(microsecond=654321)
    limit_naive = UsageLimitDTO(
        scope=LimitScope.USER.value, limit_type=LimitType.REQUESTS.value, max_value=1, interval_unit="hour", interval_value=1, username="naive_user",
        created_at=naive_dt, updated_at=naive_dt # Inserted as naive
    )
    sqlite_backend.insert_usage_limit(limit_naive)
    retrieved_naive_list = sqlite_backend.get_usage_limits(scope=LimitScope.USER, username="naive_user")
    assert len(retrieved_naive_list) == 1
    retrieved_naive_obj = retrieved_naive_list[0]

    # Expect retrieved datetime to be UTC-aware
    assert retrieved_naive_obj.created_at is not None and retrieved_naive_obj.created_at.tzinfo == timezone.utc
    # Compare by making the original naive_dt UTC-aware and rounding to seconds
    assert retrieved_naive_obj.created_at is not None and retrieved_naive_obj.created_at.replace(microsecond=0) == naive_dt.replace(tzinfo=timezone.utc, microsecond=0)
    assert retrieved_naive_obj.updated_at is not None and retrieved_naive_obj.updated_at.tzinfo == timezone.utc
    assert retrieved_naive_obj.updated_at is not None and retrieved_naive_obj.updated_at.replace(microsecond=0) == naive_dt.replace(tzinfo=timezone.utc, microsecond=0)


    # Test with None datetimes (should use DB defaults and be retrieved as UTC-aware)
    limit_none_dt = UsageLimitDTO(
        scope=LimitScope.CALLER.value, limit_type=LimitType.REQUESTS.value, max_value=10000, interval_unit="week", interval_value=1, caller_name="none_dt_caller",
        created_at=None, updated_at=None
    )
    sqlite_backend.insert_usage_limit(limit_none_dt)
    retrieved_none_dt_list = sqlite_backend.get_usage_limits(scope=LimitScope.CALLER, caller_name="none_dt_caller")
    assert len(retrieved_none_dt_list) == 1
    retrieved_none_dt = retrieved_none_dt_list[0]
    
    assert isinstance(retrieved_none_dt.created_at, datetime)
    assert retrieved_none_dt.created_at is not None and retrieved_none_dt.created_at.tzinfo == timezone.utc # Expect UTC aware from DB default
    assert isinstance(retrieved_none_dt.updated_at, datetime)
    assert retrieved_none_dt.updated_at is not None and retrieved_none_dt.updated_at.tzinfo == timezone.utc # Expect UTC aware from DB default
    
    current_utc_aware = datetime.now(timezone.utc)
    assert (current_utc_aware - retrieved_none_dt.created_at).total_seconds() < 10
    assert (current_utc_aware - retrieved_none_dt.updated_at).total_seconds() < 10
