from datetime import datetime, timezone, timedelta

import pytest
from freezegun import freeze_time

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)


@pytest.fixture
def sqlite_backend_for_accounting(tmp_path):
    db_path = str(tmp_path / "test_accounting_day.sqlite")
    backend = SQLiteBackend(db_path=db_path)
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def accounting_instance(sqlite_backend_for_accounting):
    acc = LLMAccounting(backend=sqlite_backend_for_accounting)
    yield acc


def test_account_model_requests_per_day(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test requests per day limit for a specific account and model."""
    username = "test_user_cd"
    model_name = "model_y"
    caller = "caller_rpd"

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=100, interval_unit=TimeInterval.DAY.value, interval_value=1
    )
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
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)
    accounting_instance.quota_service.refresh_limits_cache()

    with freeze_time("2023-01-01 00:00:00", tz_offset=0) as freezer:
        freezer.tick(delta=timedelta(hours=10))
        allowed, reason = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed, f"Request 1/2 for {model_name} by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model=model_name, username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

        freezer.tick(delta=timedelta(hours=1))
        allowed, reason = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed, f"Request 2/2 for {model_name} by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model=model_name, username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

        freezer.tick(delta=timedelta(hours=1))
        allowed, message = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert not allowed, f"3rd request for {model_name} by {username} should be denied"
        assert message is not None, "Denial message should not be None"
        assert f"USER (user: {username})" in message
        assert "limit: 2.00 requests per 1 day" in message
        assert "exceeded. Current usage: 2.00, request: 1.00." in message

        allowed_other_user, _ = accounting_instance.check_quota(
            model=model_name, username="other_user_rpd", caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_user, "Request for same model by other_user_rpd should be allowed"

        allowed_other_model, _ = accounting_instance.check_quota(
            model="other_model_rpd", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_model, f"Request for other_model_rpd by {username} should be allowed"


def test_account_model_completion_tokens_per_day(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test completion tokens per day limit for a specific account and model."""
    username = "test_user_gh"
    model_name = "model_a"
    caller = "caller_ctpd"

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.OUTPUT_TOKENS.value,
        max_value=5000, interval_unit=TimeInterval.DAY.value, interval_value=1
    )
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
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)
    accounting_instance.quota_service.refresh_limits_cache()

    with freeze_time("2023-01-01 00:00:00", tz_offset=0) as freezer:
        freezer.tick(delta=timedelta(seconds=0))
        allowed, reason = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=150
        )
        assert allowed, f"Request 1 (150 tokens) for {model_name} by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model=model_name, username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=150, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

        freezer.tick(delta=timedelta(seconds=1))
        allowed, message = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=51
        )
        assert not allowed, f"Request 2 (51 tokens) for {model_name} by {username} should be denied"
        assert message is not None, "Denial message should not be None"
        assert f"USER (user: {username})" in message
        assert f"limit: 200.00 {LimitType.OUTPUT_TOKENS.value} per 1 day" in message
        assert "exceeded. Current usage: 150.00, request: 51.00." in message

        allowed_other_user, _ = accounting_instance.check_quota(
            model=model_name, username="other_user_ctpd", caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_user, "Request for same model by other_user_ctpd should be allowed"

        allowed_other_model, _ = accounting_instance.check_quota(
            model="other_model_ctpd", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_model, f"Request for other_model_ctpd by {username} should be allowed"
