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


def test_multiple_limit_types(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    with freeze_time("2023-01-01 00:00:00", tz_offset=0) as freezer:
        # Setting up a token-based limit directly on the backend using UsageLimitData
        token_limit = UsageLimitDTO(
            scope=LimitScope.USER.value,
            username="user2",
            limit_type=LimitType.INPUT_TOKENS.value,
            max_value=10000,
            interval_unit=TimeInterval.DAY.value,
            interval_value=1
        )
        sqlite_backend_for_accounting.insert_usage_limit(token_limit)

        # Setting up a cost-based limit directly on the backend using UsageLimitData
        cost_limit = UsageLimitDTO(
            scope=LimitScope.USER.value,
            username="user2",
            limit_type=LimitType.COST.value,
            max_value=50.00,
            interval_unit=TimeInterval.WEEK.value,
            interval_value=1
        )
        sqlite_backend_for_accounting.insert_usage_limit(cost_limit)


        # Refresh the cache in QuotaService after inserting all limits
        accounting_instance.quota_service.refresh_limits_cache()

        # Test token limit is enforced
        # Ensure a timestamp for the check, though not strictly needed if not tracking yet
        freezer.tick(delta=timedelta(seconds=1)) # Advance time for the token check
        # current_time_token_check = datetime.now(timezone.utc) # Not strictly needed as check_quota uses frozen time
        allowed_tokens, message_tokens = accounting_instance.check_quota(
            "gpt-4", "user2", "app2", 15000, 0.0
            # project_name and completion_tokens can be omitted if not relevant to specific limits being tested
        )
        assert not allowed_tokens, "Should be denied due to token limit"
        assert message_tokens is not None, "Denial message for token limit should not be None"
        assert "USER (user: user2) limit: 10000.00 input_tokens per 1 day" in message_tokens
        assert "exceeded. Current usage: 0.00, request: 15000.00." in message_tokens

        # Clear the denial cache to ensure subsequent checks are not affected by the token limit denial
        accounting_instance.quota_service._denial_cache.clear()

        # Track some usage that is within token limits (e.g., 200 tokens) but accumulates cost.
        # This loop will also test the cost limit eventually.
        # The cache is already loaded. Each check_quota will use the cached limits.
        for i in range(49):
            freezer.tick(delta=timedelta(seconds=1)) # Advance time for each iteration
            current_timestamp_loop = datetime.now(timezone.utc)
            allowed_cost_accumulation, reason_cost_accumulation = accounting_instance.check_quota(
                "gpt-4", "user2", "app2", 200, 1.00
            )
            assert allowed_cost_accumulation, f"Request {i+1}/49 (cost accumulation) should be allowed. Reason: {reason_cost_accumulation}"
            accounting_instance.track_usage(
                model="gpt-4",
                username="user2",
                caller_name="app2",
                prompt_tokens=200,
                completion_tokens=500, # Assuming some completion tokens
                cost=1.00,
                timestamp=current_timestamp_loop
            )

        # Now, current weekly cost usage is $49.00. Limit is $50.00.
        # A request costing $1.01 should exceed the limit.
        freezer.tick(delta=timedelta(seconds=1)) # Advance time for the final cost check
        # current_time_cost_check = datetime.now(timezone.utc) # Not strictly needed
        allowed_cost, message_cost = accounting_instance.check_quota(
            "gpt-4", "user2", "app2", 200, 1.01
        )
        assert not allowed_cost, "Should be denied due to cost limit"
        assert message_cost is not None, "Denial message for cost limit should not be None"
        assert "USER (user: user2) limit: 50.00 cost per 1 week" in message_cost
        assert "exceeded. Current usage: 49.00, request: 1.01." in message_cost
