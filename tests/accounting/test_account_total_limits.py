from datetime import datetime, timezone, timedelta

import pytest
from freezegun import freeze_time

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)


@pytest.fixture
def sqlite_backend_for_accounting(tmp_path):
    db_path = str(tmp_path / "test_accounting_total.sqlite")
    backend = SQLiteBackend(db_path=db_path)
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def accounting_instance(sqlite_backend_for_accounting):
    acc = LLMAccounting(backend=sqlite_backend_for_accounting)
    yield acc


def test_account_total_requests_per_minute(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test account-wide total requests per minute, ensuring it sums across models and takes precedence."""
    username = "test_user_account_wide"
    caller = "caller_account_total"

    # Account-wide limit (no model specified)
    account_wide_limit = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username=username,
        model=None,  # Explicitly None for account-wide
        caller_name=None, # Explicitly None for account-wide
        limit_type=LimitType.REQUESTS.value,
        max_value=4,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    )
    user_model_specific_limit = UsageLimitDTO(
        scope=LimitScope.USER.value, # Could also be MODEL scope if username and model are set
        username=username,
        model="specific_model_q",
        limit_type=LimitType.REQUESTS.value,
        max_value=10, # Higher than the account-wide limit
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    )
    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=100, interval_unit=TimeInterval.MINUTE.value, interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(account_wide_limit)
    sqlite_backend_for_accounting.insert_usage_limit(user_model_specific_limit)
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)
    accounting_instance.quota_service.refresh_limits_cache()

    with freeze_time("2023-01-01 00:00:00", tz_offset=0) as freezer:
        # Track 2 requests for model_a
        for i in range(2):
            freezer.tick(delta=timedelta(seconds=1))
            allowed, reason = accounting_instance.check_quota(
                model="model_a", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
            )
            assert allowed, f"Request {i+1}/2 for model_a by {username} should be allowed. Reason: {reason}"
            accounting_instance.track_usage(
                model="model_a", username=username, caller_name=caller,
                prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
            )

        # Track 2 requests for model_b (total 4 requests for the user)
        for i in range(2):
            freezer.tick(delta=timedelta(seconds=1))
            allowed, reason = accounting_instance.check_quota(
                model="model_b", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
            )
            assert allowed, f"Request {i+1}/2 for model_b by {username} should be allowed. Reason: {reason}"
            accounting_instance.track_usage(
                model="model_b", username=username, caller_name=caller,
                prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
            )

        freezer.tick(delta=timedelta(seconds=1))

        allowed, message = accounting_instance.check_quota(
            model="model_c", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert not allowed, f"5th request for model_c by {username} should be denied by account-wide limit"
        assert message is not None, "Denial message should not be None for 5th request"
        assert f"USER (user: {username}) limit: 4.00 requests per 1 minute" in message
        assert "exceeded. Current usage: 4.00, request: 1.00." in message

        allowed_specific, message_specific = accounting_instance.check_quota(
            model="specific_model_q", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert not allowed_specific, \
            f"Request for specific_model_q by {username} should be denied by account-wide limit (already at 4 requests)"
        assert message_specific is not None, "Denial message should not be None for specific_model_q"
        assert f"USER (user: {username}) limit: 4.00 requests per 1 minute" in message_specific
        assert "exceeded. Current usage: 4.00, request: 1.00." in message_specific

        allowed_other_user, _ = accounting_instance.check_quota(
            model="model_a", username="other_user_account", caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_user, "Request for model_a by other_user_account should be allowed"
