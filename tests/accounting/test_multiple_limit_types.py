from datetime import datetime, timezone

import pytest

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimit)


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
    # Manually enter and exit context for testing purposes
    acc.__enter__()
    yield acc
    acc.__exit__(None, None, None)


def test_multiple_limit_types(accounting_instance, sqlite_backend_for_accounting):
    sqlite_backend_for_accounting.insert_usage_limit(
        UsageLimit(
            scope=LimitScope.USER.value,
            username="user2",
            limit_type=LimitType.INPUT_TOKENS.value,
            max_value=10000,
            interval_unit=TimeInterval.DAY.value,
            interval_value=1
        )
    )
    sqlite_backend_for_accounting.insert_usage_limit(
        UsageLimit(
            scope=LimitScope.USER.value,
            username="user2",
            limit_type=LimitType.COST.value,
            max_value=50.00,
            interval_unit=TimeInterval.WEEK.value,
            interval_value=1
        )
    )

    # Test token limit
    allowed, message = accounting_instance.check_quota("gpt-4", "user2", "app2", 15000, 0.0)
    assert not allowed
    assert "USER limit: 10000.00 input_tokens per 1 day" in message

    # Test cost limit
    # Add requests totaling $49.00
    for _ in range(49):
        allowed, _ = accounting_instance.check_quota("gpt-4", "user2", "app2", 200, 1.00)
        assert allowed
        accounting_instance.track_usage(
            model="gpt-4",
            username="user2",
            caller_name="app2",
            prompt_tokens=200,
            completion_tokens=500,
            cost=1.00,
            timestamp=datetime.now(timezone.utc)
        )

    # Check exceeding cost limit - should be blocked BEFORE adding
    allowed, message = accounting_instance.check_quota("gpt-4", "user2", "app2", 200, 1.01)
    assert not allowed
    assert "USER limit: 50.00 cost per 1 week" in message
