from datetime import datetime, timezone, timedelta

import pytest
from freezegun import freeze_time

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)


@pytest.fixture
def sqlite_backend_for_accounting(tmp_path):
    db_path = str(tmp_path / "test_accounting_minute.sqlite")
    backend = SQLiteBackend(db_path=db_path)
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def accounting_instance(sqlite_backend_for_accounting):
    acc = LLMAccounting(backend=sqlite_backend_for_accounting)
    yield acc


def test_account_model_requests_per_minute(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test requests per minute limit for a specific account and model."""
    username = "test_user_ab"
    model_name = "model_x"
    caller = "caller_rpm"

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=100, interval_unit=TimeInterval.MINUTE.value, interval_value=1
    )
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
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)
    accounting_instance.quota_service.refresh_limits_cache()

    with freeze_time("2023-01-01 00:00:00", tz_offset=0) as freezer:
        for i in range(3):
            freezer.tick(delta=timedelta(seconds=1))
            allowed, reason = accounting_instance.check_quota(
                model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
            )
            assert allowed, f"Request {i+1}/3 for {model_name} by {username} should be allowed. Reason: {reason}"
            accounting_instance.track_usage(
                model=model_name, username=username, caller_name=caller,
                prompt_tokens=10, completion_tokens=10, cost=0.01, timestamp=datetime.now(timezone.utc)
            )

        freezer.tick(delta=timedelta(seconds=1))
        allowed, message = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert not allowed, f"4th request for {model_name} by {username} should be denied"
        assert message is not None, "Denial message should not be None"
        assert f"USER (user: {username})" in message
        assert "limit: 3.00 requests per 1 minute" in message
        assert "exceeded. Current usage: 3.00, request: 1.00." in message

        allowed_other_user, _ = accounting_instance.check_quota(
            model=model_name, username="other_user_rpm", caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_user, "Request for same model by other_user_rpm should be allowed"

        allowed_other_model, _ = accounting_instance.check_quota(
            model="other_model_rpm", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_model, f"Request for other_model_rpm by {username} should be allowed"


def test_account_model_completion_tokens_per_minute(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    """Test completion tokens per minute limit for a specific account and model."""
    username = "test_user_ef"
    model_name = "model_z"
    caller = "caller_ctpm"

    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.OUTPUT_TOKENS.value,
        max_value=5000, interval_unit=TimeInterval.MINUTE.value, interval_value=1
    )
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
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)
    accounting_instance.quota_service.refresh_limits_cache()

    with freeze_time("2023-01-01 00:00:00", tz_offset=0) as freezer:
        freezer.tick(delta=timedelta(seconds=0))
        allowed, reason = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=500
        )
        assert allowed, f"Request 1 (500 tokens) for {model_name} by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model=model_name, username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=500, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

        freezer.tick(delta=timedelta(seconds=1))
        allowed, reason = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=500
        )
        assert allowed, f"Request 2 (500 tokens) for {model_name} by {username} should be allowed. Reason: {reason}"
        accounting_instance.track_usage(
            model=model_name, username=username, caller_name=caller,
            prompt_tokens=10, completion_tokens=500, cost=0.01, timestamp=datetime.now(timezone.utc)
        )

        freezer.tick(delta=timedelta(seconds=1))
        allowed, message = accounting_instance.check_quota(
            model=model_name, username=username, caller_name=caller, input_tokens=10, completion_tokens=1
        )
        assert not allowed, f"Request 3 (1 token) for {model_name} by {username} should be denied"
        assert message is not None, "Denial message should not be None"
        assert f"USER (user: {username})" in message
        assert f"limit: 1000.00 {LimitType.OUTPUT_TOKENS.value} per 1 minute" in message
        assert "exceeded. Current usage: 1000.00, request: 1.00." in message

        allowed_other_user, _ = accounting_instance.check_quota(
            model=model_name, username="other_user_ctpm", caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_user, "Request for same model by other_user_ctpm should be allowed"

        allowed_other_model, _ = accounting_instance.check_quota(
            model="other_model_ctpm", username=username, caller_name=caller, input_tokens=10, completion_tokens=10
        )
        assert allowed_other_model, f"Request for other_model_ctpm by {username} should be allowed"
