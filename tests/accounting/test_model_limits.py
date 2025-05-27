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


def test_model_limit_priority(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    # Setting up a global limit directly on the backend using UsageLimitData
    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value,
        limit_type=LimitType.REQUESTS.value,
        max_value=100,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)

    # Setting up a model-specific limit directly on the backend using UsageLimitData
    model_limit = UsageLimitDTO(
        scope=LimitScope.MODEL.value,
        model="gpt-4",
        limit_type=LimitType.REQUESTS.value,
        max_value=5,
        interval_unit=TimeInterval.HOUR.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(model_limit)

    # Make 5 requests that should be allowed by the model-specific limit
    for i in range(5):
        allowed, reason = accounting_instance.check_quota("gpt-4", "user1", "app1", 1000, 0.25)
        assert allowed, f"Request {i+1}/5 for gpt-4 should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model="gpt-4",
            username="user1",
            caller_name="app1",
            prompt_tokens=1000,
            completion_tokens=500,
            cost=0.25,
            timestamp=datetime.now(timezone.utc)
        )

    # Check 6th request for "gpt-4" should be blocked by the model-specific limit
    allowed, message = accounting_instance.check_quota("gpt-4", "user1", "app1", 1000, 0.25)
    assert not allowed, "6th request for gpt-4 should be denied by model limit"
    assert message is not None, "Denial message should not be None for gpt-4"
    
    expected_message_part_1 = "MODEL (model: gpt-4) limit: 5.00 requests per 1 hour"
    expected_message_part_2 = "current usage: 5.00, request: 1.00"
    
    assert expected_message_part_1 in message
    assert expected_message_part_2 in message

    # Check that a different model is still subject to the global limit (if no model-specific one exists for it)
    allowed_other_model, reason_other_model = accounting_instance.check_quota("gpt-3.5-turbo", "user1", "app1", 100, 0.01)
    assert allowed_other_model, f"Request for gpt-3.5-turbo should be allowed. Reason: {reason_other_model}"
