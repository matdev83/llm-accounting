from datetime import datetime, timezone, timedelta

import pytest

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)


@pytest.fixture
def sqlite_backend_for_accounting(tmp_path): # Changed temp_db_path to tmp_path for standard pytest fixture
    """Create and initialize a SQLite backend for LLMAccounting"""
    db_path = str(tmp_path / "test_accounting.sqlite")
    backend = SQLiteBackend(db_path=db_path)
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def accounting_instance(sqlite_backend_for_accounting):
    """Create an LLMAccounting instance with a temporary SQLite backend"""
    acc = LLMAccounting(backend=sqlite_backend_for_accounting)
    yield acc


def test_account_model_requests_per_minute(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test requests per minute limit for a specific account and model."""
    username = "test_user_ab"
    model_name = "model_x"
    caller = "caller_rpm"

    account_model_limit = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username=username,
        model=model_name,
        limit_type=LimitType.REQUESTS.value,
        max_value=3,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(account_model_limit)

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=100, interval_unit=TimeInterval.MINUTE.value, interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)

    for i in range(3):
        allowed, reason = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed, f"Request {i+1}/3 for {model_name} by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model=model_name, username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

    allowed, message = accounting_instance.check_quota(
        model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert not allowed, f"4th request for {model_name} by {username} should be denied"
    assert message is not None, "Denial message should not be None"
    assert f"USER (model: {model_name}, user: {username})" in message  # Adjusted order
    assert "limit: 3.00 requests per 1 minute" in message
    assert "current usage: 3.00, request: 1.00" in message

    allowed_other_user, _ = accounting_instance.check_quota(
        model=model_name, username="other_user_rpm", caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_user, "Request for same model by other_user_rpm should be allowed"

    allowed_other_model, _ = accounting_instance.check_quota(
        model="other_model_rpm", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_model, f"Request for other_model_rpm by {username} should be allowed"


def test_account_model_requests_per_day(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test requests per day limit for a specific account and model."""
    username = "test_user_cd"
    model_name = "model_y"
    caller = "caller_rpd"

    account_model_limit = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username=username,
        model=model_name,
        limit_type=LimitType.REQUESTS.value,
        max_value=2,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(account_model_limit)

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=100, interval_unit=TimeInterval.DAY.value, interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)

    for i in range(2):
        allowed, reason = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed, f"Request {i+1}/2 for {model_name} by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model=model_name, username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

    allowed, message = accounting_instance.check_quota(
        model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert not allowed, f"3rd request for {model_name} by {username} should be denied"
    assert message is not None, "Denial message should not be None"
    assert f"USER (model: {model_name}, user: {username})" in message  # Adjusted order
    assert "limit: 2.00 requests per 1 day" in message
    assert "current usage: 2.00, request: 1.00" in message

    allowed_other_user, _ = accounting_instance.check_quota(
        model=model_name, username="other_user_rpd", caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_user, "Request for same model by other_user_rpd should be allowed"

    allowed_other_model, _ = accounting_instance.check_quota(
        model="other_model_rpd", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_model, f"Request for other_model_rpd by {username} should be allowed"


def test_account_model_completion_tokens_per_minute(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test completion tokens per minute limit for a specific account and model."""
    username = "test_user_ef"
    model_name = "model_z"
    caller = "caller_ctpm"

    account_model_limit = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username=username,
        model=model_name,
        limit_type=LimitType.OUTPUT_TOKENS.value,
        max_value=1000,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(account_model_limit)

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.OUTPUT_TOKENS.value,
        max_value=5000, interval_unit=TimeInterval.MINUTE.value, interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)

    # First request: 500 tokens
    allowed, reason = accounting_instance.check_quota(
        model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=500
    )
    assert allowed, f"Request 1 (500 tokens) for {model_name} by {username} should be allowed. Reason: {reason}"
    accounting_instance.track_usage(
        model=model_name, username=username, caller_name=caller,
        prompt_tokens=10, completion_tokens=500, cost=0.01, timestamp=datetime.now(timezone.utc)
    )

    # Second request: 500 tokens (total 1000)
    allowed, reason = accounting_instance.check_quota(
        model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=500
    )
    assert allowed, f"Request 2 (500 tokens) for {model_name} by {username} should be allowed. Reason: {reason}"
    accounting_instance.track_usage(
        model=model_name, username=username, caller_name=caller,
        prompt_tokens=10, completion_tokens=500, cost=0.01, timestamp=datetime.now(timezone.utc)
    )

    # Third request: 1 token (total 1001 - should be denied)
    allowed, message = accounting_instance.check_quota(
        model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=1
    )
    assert not allowed, f"Request 3 (1 token) for {model_name} by {username} should be denied"
    assert message is not None, "Denial message should not be None"
    assert f"USER (model: {model_name}, user: {username})" in message  # Adjusted order
    assert f"limit: 1000.00 {LimitType.OUTPUT_TOKENS.value} per 1 minute" in message
    assert "current usage: 1000.00, request: 1.00" in message

    allowed_other_user, _ = accounting_instance.check_quota(
        model=model_name, username="other_user_ctpm", caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_user, "Request for same model by other_user_ctpm should be allowed"

    allowed_other_model, _ = accounting_instance.check_quota(
        model="other_model_ctpm", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_model, f"Request for other_model_ctpm by {username} should be allowed"


def test_account_model_completion_tokens_per_day(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test completion tokens per day limit for a specific account and model."""
    username = "test_user_gh"
    model_name = "model_a"
    caller = "caller_ctpd"

    account_model_limit = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username=username,
        model=model_name,
        limit_type=LimitType.OUTPUT_TOKENS.value,
        max_value=200,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(account_model_limit)

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.OUTPUT_TOKENS.value,
        max_value=5000, interval_unit=TimeInterval.DAY.value, interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)

    # First request: 150 tokens
    allowed, reason = accounting_instance.check_quota(
        model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=150
    )
    assert allowed, f"Request 1 (150 tokens) for {model_name} by {username} should be allowed. Reason: {reason}"
    accounting_instance.track_usage(
        model=model_name, username=username, caller_name=caller,
        prompt_tokens=10, completion_tokens=150, cost=0.01, timestamp=datetime.now(timezone.utc)
    )

    # Second request: 51 tokens (total 201 - should be denied)
    allowed, message = accounting_instance.check_quota(
        model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=51
    )
    assert not allowed, f"Request 2 (51 tokens) for {model_name} by {username} should be denied"
    assert message is not None, "Denial message should not be None"
    assert f"USER (model: {model_name}, user: {username})" in message # Adjusted order
    assert f"limit: 200.00 {LimitType.OUTPUT_TOKENS.value} per 1 day" in message
    assert "current usage: 150.00, request: 51.00" in message


    allowed_other_user, _ = accounting_instance.check_quota(
        model=model_name, username="other_user_ctpd", caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_user, "Request for same model by other_user_ctpd should be allowed"

    allowed_other_model, _ = accounting_instance.check_quota(
        model="other_model_ctpd", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_model, f"Request for other_model_ctpd by {username} should be allowed"


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
    sqlite_backend_for_accounting.insert_usage_limit(account_wide_limit)

    # Higher (user, model) specific limit for the same user but one specific model
    user_model_specific_limit = UsageLimitDTO(
        scope=LimitScope.USER.value, # Could also be MODEL scope if username and model are set
        username=username,
        model="specific_model_q",
        limit_type=LimitType.REQUESTS.value,
        max_value=10, # Higher than the account-wide limit
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(user_model_specific_limit)

    # Global limit to ensure account-wide is being tested
    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=100, interval_unit=TimeInterval.MINUTE.value, interval_value=1
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)

    # Track 2 requests for model_a
    for i in range(2):
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
        allowed, reason = accounting_instance.check_quota(
            model="model_b", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed, f"Request {i+1}/2 for model_b by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model="model_b", username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

    # Attempt a 5th request for model_c - should be denied by account-wide limit
    allowed, message = accounting_instance.check_quota(
        model="model_c", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert not allowed, f"5th request for model_c by {username} should be denied by account-wide limit"
    assert message is not None, "Denial message should not be None for 5th request"
    # Message should be from the account-wide limit (user: test_user_account_wide, no model)
    assert f"USER (user: {username}) limit: 4.00 requests per 1 minute" in message
    assert "current usage: 4.00, request: 1.00" in message

    # Attempt a request for "specific_model_q"
    # This should also be denied by the account-wide limit as the user's total is 4.
    allowed_specific, message_specific = accounting_instance.check_quota(
        model="specific_model_q", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert not allowed_specific, \
        f"Request for specific_model_q by {username} should be denied by account-wide limit (already at 4 requests)"
    assert message_specific is not None, "Denial message should not be None for specific_model_q"
    assert f"USER (user: {username}) limit: 4.00 requests per 1 minute" in message_specific
    assert "current usage: 4.00, request: 1.00" in message_specific


    # Verify that a different user is allowed
    allowed_other_user, _ = accounting_instance.check_quota(
        model="model_a", username="other_user_account", caller_name=caller, input_tokens=10, completion_tokens=10
    )
    assert allowed_other_user, "Request for model_a by other_user_account should be allowed"

# End of tests/accounting/test_account_model_limits.py
