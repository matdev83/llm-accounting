from datetime import datetime, timezone

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


def test_user_caller_combination(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    # Setting up a caller-specific limit directly on the backend using UsageLimitData
    caller_limit = UsageLimitDTO(
        scope=LimitScope.CALLER.value,
        username="user1",
        caller_name="app1",
        limit_type=LimitType.REQUESTS.value,
        max_value=3,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(caller_limit)

    # Make 3 allowed requests for user1, app1
    for i in range(3):
        allowed, reason = accounting_instance.check_quota("gpt-3", "user1", "app1", 1000, 0.25)
        assert allowed, f"Request {i+1}/3 for user1/app1 should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model="gpt-3",
            username="user1",
            caller_name="app1",
            prompt_tokens=1000,
            completion_tokens=500,
            cost=0.25,
            timestamp=datetime.now(timezone.utc)
        )

    # Make 4th request for user1, app1, which should be blocked
    allowed, message = accounting_instance.check_quota("gpt-3", "user1", "app1", 1000, 0.25)
    assert not allowed, "4th request for user1/app1 should be denied"
    assert message is not None, "Denial message for user1/app1 should not be None"
    assert "CALLER (user: user1, caller: app1) limit: 3.00 requests per 1 day" in message
    assert "current usage: 3.00, request: 1.00" in message

    # Test that another user (user2) with the same caller (app1) is not affected by user1's limit
    allowed_user2, reason_user2 = accounting_instance.check_quota("gpt-3", "user2", "app1", 500, 0.10)
    assert allowed_user2, f"Request for user2/app1 should be allowed. Reason: {reason_user2}"

    # Test that user1 with a different caller (app2) is not affected by user1/app1 limit
    allowed_app2, reason_app2 = accounting_instance.check_quota("gpt-3", "user1", "app2", 500, 0.10)
    assert allowed_app2, f"Request for user1/app2 should be allowed. Reason: {reason_app2}"
