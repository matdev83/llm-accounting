from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import pytest

from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)
from llm_accounting.services.quota_service import QuotaService
from llm_accounting.backends.base import TransactionalBackend


@pytest.fixture
def mock_backend() -> MagicMock:
    """Provides a MagicMock instance for TransactionalBackend."""
    backend = MagicMock(spec=TransactionalBackend)
    backend.get_usage_limits.return_value = []
    return backend


def test_check_quota_no_limits(mock_backend: MagicMock):
    """Test check_quota when no limits are configured (cache is empty)."""
    quota_service = QuotaService(mock_backend)

    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01
    )

    assert is_allowed is True
    assert reason is None
    mock_backend.get_usage_limits.assert_called_once()


def test_check_quota_allowed_single_limit(mock_backend: MagicMock):
    """Test check_quota when usage is within a single configured limit."""
    now = datetime.now(timezone.utc)
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 5.0

    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01
    )

    assert is_allowed is True
    assert reason is None

    mock_backend.get_usage_limits.assert_called_once()
    mock_backend.get_accounting_entries_for_quota.assert_called_once()
    kwargs = mock_backend.get_accounting_entries_for_quota.call_args.kwargs
    assert kwargs['limit_type'] == LimitType.COST
    assert kwargs['username'] == "test_user"


def test_check_quota_denied_single_limit(mock_backend: MagicMock):
    """Test check_quota when usage exceeds a single configured limit."""
    now = datetime.now(timezone.utc)
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    # Instantiate QuotaService AFTER setting the mock return value.
    # The first call to check_quota will load the cache if it's None.
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 9.99

    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=0, cost=0.02
    )

    assert is_allowed is False
    assert reason is not None
    assert "USER (user: test_user) limit: 10.00 cost per 1 month" in reason
    assert "exceeded. Current usage: 9.99, request: 0.02." in reason

    mock_backend.get_usage_limits.assert_called_once()
    mock_backend.get_accounting_entries_for_quota.assert_called_once()


def test_check_quota_multiple_limits_one_exceeded(mock_backend: MagicMock):
    """Test check_quota with multiple limits, where one is exceeded."""
    now = datetime.now(timezone.utc)
    cost_limit_user = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    request_limit_user = UsageLimitDTO(
        id=2, scope=LimitScope.USER.value, limit_type=LimitType.REQUESTS.value,
        max_value=100.0, interval_unit=TimeInterval.DAY.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [cost_limit_user, request_limit_user]
    quota_service = QuotaService(mock_backend)

    def get_accounting_side_effect(start_time, end_time, limit_type, interval_unit, model, username, caller_name, project_name, filter_project_null):
        if limit_type == LimitType.COST and username == "test_user":
            return 5.0
        elif limit_type == LimitType.REQUESTS and username == "test_user":
            return 100.0
        return 0.0

    mock_backend.get_accounting_entries_for_quota.side_effect = get_accounting_side_effect

    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=10, cost=0.01
    )

    assert is_allowed is False
    assert reason is not None
    assert "USER (user: test_user) limit: 100.00 requests per 1 day" in reason
    assert "exceeded. Current usage: 100.00, request: 1.00." in reason

    mock_backend.get_usage_limits.assert_called_once()
    assert mock_backend.get_accounting_entries_for_quota.call_count == 2


def test_check_quota_different_scopes_in_cache(mock_backend: MagicMock):
    """Test that QuotaService correctly filters from cache for different scopes."""
    now = datetime.now(timezone.utc)
    global_req_limit = UsageLimitDTO(id=1, scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value, max_value=5, interval_unit=TimeInterval.MINUTE.value, interval_value=1)
    user_cost_limit = UsageLimitDTO(id=2, scope=LimitScope.USER.value, username="test_user", limit_type=LimitType.COST.value, max_value=10, interval_unit=TimeInterval.DAY.value, interval_value=1)
    model_token_limit = UsageLimitDTO(id=3, scope=LimitScope.MODEL.value, model="gpt-4", limit_type=LimitType.INPUT_TOKENS.value, max_value=1000, interval_unit=TimeInterval.HOUR.value, interval_value=1)

    mock_backend.get_usage_limits.return_value = [global_req_limit, user_cost_limit, model_token_limit]
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 5.0

    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="super_caller",
        input_tokens=1, cost=0.001
    )

    assert not is_allowed
    assert "GLOBAL limit: 5.00 requests per 1 minute" in reason

    mock_backend.get_usage_limits.assert_called_once()
    assert mock_backend.get_accounting_entries_for_quota.call_count == 3
    call_kwargs_list = [call.kwargs for call in mock_backend.get_accounting_entries_for_quota.call_args_list]
    assert any(kw['limit_type'] == LimitType.REQUESTS and kw['model'] is None and kw['username'] is None for kw in call_kwargs_list)


def test_check_quota_token_limits(mock_backend: MagicMock):
    """Test check_quota for input token limits from cache."""
    now = datetime.now(timezone.utc)
    model_token_limit = UsageLimitDTO(
        id=1, scope=LimitScope.MODEL.value, limit_type=LimitType.INPUT_TOKENS.value,
        max_value=1000.0, interval_unit=TimeInterval.HOUR.value, interval_value=1,
        model="text-davinci-003", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [model_token_limit]
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 950.0

    is_allowed, reason = quota_service.check_quota(
        model="text-davinci-003", username="any_user", caller_name="any_caller",
        input_tokens=50, cost=0.0
    )
    assert is_allowed is True
    assert reason is None
    mock_backend.get_accounting_entries_for_quota.assert_called_with(
        start_time=mock_backend.get_accounting_entries_for_quota.call_args.kwargs['start_time'],
        end_time=mock_backend.get_accounting_entries_for_quota.call_args.kwargs['end_time'],
        limit_type=LimitType.INPUT_TOKENS,
        interval_unit=mock_backend.get_accounting_entries_for_quota.call_args.kwargs['interval_unit'],
        model="text-davinci-003",
        username=None, caller_name=None, project_name=None, filter_project_null=None
    )

    mock_backend.get_accounting_entries_for_quota.reset_mock()
    mock_backend.get_accounting_entries_for_quota.return_value = 950.0

    is_allowed, reason = quota_service.check_quota(
        model="text-davinci-003", username="any_user", caller_name="any_caller",
        input_tokens=51, cost=0.0
    )
    assert is_allowed is False
    assert reason is not None
    assert "MODEL (model: text-davinci-003) limit: 1000.00 input_tokens per 1 hour" in reason
    assert "exceeded. Current usage: 950.00, request: 51.00." in reason

    mock_backend.get_usage_limits.assert_called_once()
    assert mock_backend.get_accounting_entries_for_quota.call_count == 1


def test_check_quota_total_token_limits(mock_backend: MagicMock):
    """Test check_quota for total token limits."""
    now = datetime.now(timezone.utc)
    total_token_limit = UsageLimitDTO(
        id=1,
        scope=LimitScope.USER.value,
        limit_type=LimitType.TOTAL_TOKENS.value,
        max_value=500.0,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
        username="user_total",
        created_at=now,
        updated_at=now,
    )
    mock_backend.get_usage_limits.return_value = [total_token_limit]
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 480.0

    is_allowed, reason = quota_service.check_quota(
        model="model-a",
        username="user_total",
        caller_name="caller",
        input_tokens=10,
        cost=0.0,
        completion_tokens=5,
    )
    assert is_allowed is True
    assert reason is None

    mock_backend.get_accounting_entries_for_quota.reset_mock()
    mock_backend.get_accounting_entries_for_quota.return_value = 490.0

    is_allowed, reason = quota_service.check_quota(
        model="model-a",
        username="user_total",
        caller_name="caller",
        input_tokens=15,
        cost=0.0,
        completion_tokens=10,
    )
    assert not is_allowed
    assert reason is not None
    assert "USER (user: user_total) limit: 500.00 total_tokens per 1 day" in reason
    assert "exceeded. Current usage: 490.00, request: 25.00." in reason

    mock_backend.get_usage_limits.assert_called()
    assert mock_backend.get_accounting_entries_for_quota.call_count == 1
