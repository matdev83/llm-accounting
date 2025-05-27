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


def test_multiple_limit_types(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    # Setting up a token-based limit directly on the backend using UsageLimitData
    token_limit = UsageLimitData(
        scope=LimitScope.USER.value,
        username="user2",
        limit_type=LimitType.INPUT_TOKENS.value,
        max_value=10000,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(token_limit)

    # Setting up a cost-based limit directly on the backend using UsageLimitData
    cost_limit = UsageLimitData(
        scope=LimitScope.USER.value,
        username="user2",
        limit_type=LimitType.COST.value,
        max_value=50.00,
        interval_unit=TimeInterval.WEEK.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(cost_limit)

    # Test token limit is enforced
    # Requesting 15000 tokens, limit is 10000
    allowed_tokens, message_tokens = accounting_instance.check_quota("gpt-4", "user2", "app2", 15000, 0.0)
    assert not allowed_tokens, "Should be denied due to token limit"
    assert message_tokens is not None, "Denial message for token limit should not be None"
    # Updated assertion to match the detailed message format
    assert "USER (user: user2) limit: 10000.00 input_tokens per 1 day" in message_tokens
    assert "current usage: 0.00, request: 15000.00" in message_tokens

    # Track some usage that is within token limits (e.g., 200 tokens) but accumulates cost.
    # This is to set up for the cost limit test.
    # We need to ensure that the usage tracked here doesn't violate the token limit setup if we were to check it.
    # For this test, we assume the token limit is high enough that the 49 * 200 tokens below won't hit it daily.
    # The primary check for token limit was above.

    # Test cost limit by accumulating usage
    # Add requests totaling $49.00 (49 requests * $1.00 each)
    for i in range(49):
        # For these checks, we assume tokens are low enough not to hit the daily token limit
        # (e.g., 200 tokens per request, total 49*200 = 9800, which is < 10000 daily token limit)
        allowed_cost_accumulation, reason_cost_accumulation = accounting_instance.check_quota("gpt-4", "user2", "app2", 200, 1.00)
        assert allowed_cost_accumulation, f"Request {i+1}/49 (cost accumulation) should be allowed. Reason: {reason_cost_accumulation}"
        accounting_instance.track_usage(
            model="gpt-4",
            username="user2",
            caller_name="app2",
            prompt_tokens=200, # Within token limits for a single request
            completion_tokens=500, # Not limited by this test's setup
            cost=1.00,
            timestamp=datetime.now(timezone.utc)
        )

    # Now, current weekly cost usage is $49.00. Limit is $50.00.
    # A request costing $1.01 should exceed the limit.
    allowed_cost, message_cost = accounting_instance.check_quota("gpt-4", "user2", "app2", 200, 1.01) # Tokens are 200, still fine for daily limit
    assert not allowed_cost, "Should be denied due to cost limit"
    assert message_cost is not None, "Denial message for cost limit should not be None"
    # Updated assertion to match the detailed message format
    assert "USER (user: user2) limit: 50.00 cost per 1 week" in message_cost
    assert "current usage: 49.00, request: 1.01" in message_cost
