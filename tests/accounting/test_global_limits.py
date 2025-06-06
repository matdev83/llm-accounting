from datetime import datetime, timezone, timedelta
from freezegun import freeze_time
import pytest

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)


@pytest.fixture
def sqlite_backend_for_accounting(temp_db_path):
    """Create and initialize a SQLite backend for LLMAccounting"""
    backend = SQLiteBackend(db_path=temp_db_path)
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def accounting_instance(sqlite_backend_for_accounting):
    """Create an LLMAccounting instance with a temporary SQLite backend"""
    acc = LLMAccounting(backend=sqlite_backend_for_accounting)
    acc.__enter__() 
    yield acc
    acc.__exit__(None, None, None)


def test_global_limit(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    with freeze_time("2023-01-01 12:00:00", tz_offset=0) as freezer: # Use as context manager
        # Use the backend directly to add UsageLimitData for setup
        limit_to_set = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=10,
            interval_unit=TimeInterval.MINUTE.value,
            interval_value=1
        )
        sqlite_backend_for_accounting.insert_usage_limit(limit_to_set)


        # Refresh the cache in QuotaService after inserting limits directly into DB
        accounting_instance.quota_service.refresh_limits_cache()

        # Check and add requests sequentially using accounting_instance
        for i in range(10):
            freezer.tick(delta=timedelta(seconds=1)) # Advance time by 1 second for each iteration
            current_timestamp = datetime.now(timezone.utc) # Define before check_quota
            allowed, reason = accounting_instance.check_quota(
                "gpt-4", "user1", "app1", 1000, 0.25
            )
            assert allowed, f"Request {i+1}/10 should be allowed. Reason: {reason}"
            accounting_instance.track_usage(
                model="gpt-4",
                username="user1",
                caller_name="app1",
                prompt_tokens=1000,
                completion_tokens=500,
                cost=0.25,
                timestamp=current_timestamp # Use the same timestamp for track_usage
            )

        # Add 11th request to exceed limit
        allowed, message = accounting_instance.check_quota("gpt-4", "user1", "app1", 1000, 0.25)
        assert not allowed, "11th request should be denied"
        assert message is not None, "Denial message should not be None"
        
        expected_message_part_1 = "GLOBAL limit: 10.00 requests per 1 minute"
        expected_message_part_2 = "exceeded. Current usage: 10.00, request: 1.00."
        
        assert expected_message_part_1 in message
        assert expected_message_part_2 in message
