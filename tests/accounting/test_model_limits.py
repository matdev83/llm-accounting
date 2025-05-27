from datetime import datetime, timezone

import pytest

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
# Updated import: UsageLimit changed to UsageLimitData
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitData)


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
    global_limit = UsageLimitData(
        scope=LimitScope.GLOBAL.value,
        limit_type=LimitType.REQUESTS.value,
        max_value=100, # Global limit is high
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)

    # Setting up a model-specific limit directly on the backend using UsageLimitData
    model_limit = UsageLimitData(
        scope=LimitScope.MODEL.value,
        model="gpt-4",
        limit_type=LimitType.REQUESTS.value,
        max_value=5, # Model limit is lower
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
    # Updated assertion to match the detailed message format
    assert "MODEL (model: gpt-4) limit: 5.00 requests per 1 hour" in message
    assert "current usage: 5.00, request: 1.00" in message

    # Check that a different model is still subject to the global limit (if no model-specific one exists for it)
    # For this, we'd need to make enough requests to hit global, or ensure it's allowed if under global.
    # Let's test if a request to "gpt-3.5-turbo" is allowed (should be, as it's under global limit of 100)
    # Assuming 5 requests for gpt-4 already happened.
    allowed_other_model, reason_other_model = accounting_instance.check_quota("gpt-3.5-turbo", "user1", "app1", 100, 0.01)
    assert allowed_other_model, f"Request for gpt-3.5-turbo should be allowed. Reason: {reason_other_model}"
    
    # If we wanted to test hitting the global limit with "gpt-3.5-turbo", we'd make more requests.
    # For example, 95 more requests to "gpt-3.5-turbo" after the 5 "gpt-4" requests.
    # The total requests would then be 5 (gpt-4) + 1 (current gpt-3.5) = 6, well under global 100.
    # This part of the test implicitly confirms that gpt-3.5-turbo is not affected by gpt-4's specific limit.
