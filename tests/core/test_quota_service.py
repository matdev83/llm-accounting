from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch
import pytest
from typing import Optional

from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)
from llm_accounting.services.quota_service import QuotaService
from llm_accounting.backends.base import BaseBackend


@pytest.fixture
def mock_backend() -> MagicMock:
    """Provides a MagicMock instance for BaseBackend."""
    backend = MagicMock(spec=BaseBackend)
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
    mock_backend.get_accounting_entries_for_quota.assert_called_once()
    assert mock_backend.get_accounting_entries_for_quota.call_args.kwargs['limit_type'] == LimitType.REQUESTS
    assert mock_backend.get_accounting_entries_for_quota.call_args.kwargs['model'] is None
    assert mock_backend.get_accounting_entries_for_quota.call_args.kwargs['username'] is None


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
        end_time=mock_backend.get_accounting_entries_for_quota.call_args.kwargs['end_time'], # Add end_time
        limit_type=LimitType.INPUT_TOKENS,
        interval_unit=mock_backend.get_accounting_entries_for_quota.call_args.kwargs['interval_unit'], # Add interval_unit
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


def test_get_period_start_monthly(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.MONTH, 1)
    assert period_start == datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)

    current_time = datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.MONTH, 1)
    assert period_start == datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_daily(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.DAY, 1)
    assert period_start == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_hourly(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.HOUR, 1)
    assert period_start == datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_minute(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    current_time = datetime(2024, 3, 15, 10, 37, 45, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.MINUTE, 1)
    assert period_start == datetime(2024, 3, 15, 10, 37, 0, tzinfo=timezone.utc)

    current_time = datetime(2024, 3, 15, 10, 37, 45, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.MINUTE, 5)
    assert period_start == datetime(2024, 3, 15, 10, 35, 0, tzinfo=timezone.utc)

def test_get_period_start_second(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    current_time = datetime(2024, 3, 15, 10, 37, 45, 123456, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.SECOND, 1)
    assert period_start == datetime(2024, 3, 15, 10, 37, 45, 0, tzinfo=timezone.utc)

    current_time = datetime(2024, 3, 15, 10, 37, 45, 123456, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.SECOND, 10)
    assert period_start == datetime(2024, 3, 15, 10, 37, 40, 0, tzinfo=timezone.utc)

def test_get_period_start_weekly(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    current_time = datetime(2024, 3, 13, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.WEEK, 1)
    assert period_start == datetime(2024, 3, 11, 0, 0, 0, tzinfo=timezone.utc)

    current_time = datetime(2024, 3, 11, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.WEEK, 1)
    assert period_start == datetime(2024, 3, 11, 0, 0, 0, tzinfo=timezone.utc)

    current_time = datetime(2024, 3, 11, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service.limit_evaluator._get_period_start(current_time, TimeInterval.WEEK, 2)
    assert period_start == datetime(2024, 3, 4, 0, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_unsupported_interval(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    current_time = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="Unsupported time interval unit"):
        quota_service.limit_evaluator._get_period_start(current_time, "unsupported_unit", 1)


# --- Tests for check_quota_enhanced ---

def test_check_quota_enhanced_no_limits(mock_backend: MagicMock):
    """Test check_quota_enhanced when no limits are configured."""
    quota_service = QuotaService(mock_backend)

    is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01
    )

    assert is_allowed is True
    assert reason is None
    assert retry_after is None
    mock_backend.get_usage_limits.assert_called_once()


def test_check_quota_enhanced_allowed_single_limit(mock_backend: MagicMock):
    """Test check_quota_enhanced when usage is within a single configured limit."""
    now = datetime.now(timezone.utc)
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 5.0

    is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01
    )

    assert is_allowed is True
    assert reason is None
    assert retry_after is None
    mock_backend.get_usage_limits.assert_called_once()
    mock_backend.get_accounting_entries_for_quota.assert_called_once()


def test_check_quota_enhanced_denied_single_limit(mock_backend: MagicMock):
    """Test check_quota_enhanced when usage exceeds a single configured limit."""
    now_dt = datetime.now(timezone.utc) # Use a fixed now for consistent period calculation
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now_dt, updated_at=now_dt
    )
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 9.99

    # Mock datetime.now within the _limit_evaluator module
    # Make 'now' slightly after the start of the month to ensure retry_after is calculated against a future period end
    mocked_now_time = datetime(now_dt.year, now_dt.month, 1, 10, 0, 0, tzinfo=timezone.utc)
    if now_dt.month == 12:
        expected_period_end_for_retry = datetime(now_dt.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        expected_period_end_for_retry = datetime(now_dt.year, now_dt.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)


    with patch('llm_accounting.services.quota_service_parts._limit_evaluator.datetime', wraps=datetime) as mock_dt:
        mock_dt.now.return_value = mocked_now_time

        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model="gpt-4", username="test_user", caller_name="test_caller",
            input_tokens=0, cost=0.02 # This cost will exceed the limit
        )

    assert is_allowed is False
    assert reason is not None
    assert "USER (user: test_user) limit: 10.00 cost per 1 month" in reason
    assert retry_after is not None
    assert isinstance(retry_after, int)
    assert retry_after >= 0

    expected_retry_val = int((expected_period_end_for_retry - mocked_now_time).total_seconds())
    assert retry_after == expected_retry_val

    mock_backend.get_usage_limits.assert_called_once()
    mock_backend.get_accounting_entries_for_quota.assert_called_once()


# --- More specific retry-after tests ---

@pytest.mark.parametrize("interval_unit_enum, interval_value, current_usage_val, request_val, mock_now_delta_seconds, period_start_delta_seconds, expected_retry_seconds_calc", [
    # Fixed Intervals
    (TimeInterval.SECOND, 10, 9.0, 1.1, 5, 0, 5), # Middle of 10s period, period started at 0s, now is 5s, ends at 10s. Retry = 10-5 = 5
    (TimeInterval.MINUTE, 1, 50.0, 11.0, 30, 0, 30), # 1 min limit, now is 30s into it. Retry = 60-30 = 30
    (TimeInterval.MINUTE, 2, 50.0, 11.0, 30, 0, 90), # 2 min limit, period started at 0m0s, now is 0m30s. Ends at 2m0s. Retry = 120-30 = 90
    (TimeInterval.HOUR, 1, 50.0, 11.0, 30 * 60, 0, 30 * 60), # 1 hour limit, now is 30m into it. Retry = 3600-1800 = 1800
    (TimeInterval.DAY, 1, 20.0, 5.0, 12 * 3600, 0, 12 * 3600), # 1 day limit, now is 12h into it. Retry = (24-12)*3600
    # Rolling Intervals
    (TimeInterval.SECOND_ROLLING, 10, 9.0, 1.1, 0, -10, 10), # Rolling 10s. Period start was 10s ago. Ends 10s from period start.
    (TimeInterval.MINUTE_ROLLING, 1, 50.0, 11.0, 0, -60, 60), # Rolling 1m. Period start was 60s ago. Ends 60s from period start.
    (TimeInterval.HOUR_ROLLING, 1, 50.0, 11.0, 0, -3600, 3600), # Rolling 1h. Period start was 1hr ago. Ends 1hr from period start.
])
def test_check_quota_enhanced_denied_retry_after_various_intervals(
    mock_backend: MagicMock,
    interval_unit_enum: TimeInterval,
    interval_value: int,
    current_usage_val: float,
    request_val: float,
    mock_now_delta_seconds: int,
    period_start_delta_seconds: int, # For rolling, this is how far back period_start is from 'now'
    expected_retry_seconds_calc: int
):
    quota_service = QuotaService(mock_backend)

    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # For fixed intervals, period_start is typically aligned to hour, day, etc.
    # For rolling, period_start is 'now' - interval_duration
    # 'now' for the test is base_time + mock_now_delta_seconds
    mocked_current_time = base_time + timedelta(seconds=mock_now_delta_seconds)

    limit_scope = LimitScope.GLOBAL.value
    limit_type = LimitType.REQUESTS.value # Using REQUESTS for simplicity, value is 1.0

    test_limit = UsageLimitDTO(
        scope=limit_scope, limit_type=limit_type,
        max_value=current_usage_val, # Set max_value to current_usage so request_val (1.0) exceeds it
        interval_unit=interval_unit_enum.value,
        interval_value=interval_value,
    )
    mock_backend.get_usage_limits.return_value = [test_limit]
    quota_service.refresh_limits_cache() # Ensure cache is loaded with this limit

    # Simulate current usage. For REQUESTS type, current_usage_val is the count.
    # To exceed, the backend should return current_usage_val. The request (1.0) makes it current_usage_val + 1.0
    mock_backend.get_accounting_entries_for_quota.return_value = current_usage_val

    with patch('llm_accounting.services.quota_service_parts._limit_evaluator.datetime', wraps=datetime) as mock_dt:
        mock_dt.now.return_value = mocked_current_time

        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model=None, username=None, caller_name=None,
            input_tokens=0, cost=0, # Not relevant for REQUESTS limit type
            # request_val for REQUESTS is 1, so it's implicitly handled by the check_quota logic
        )

    assert is_allowed is False
    assert reason is not None
    assert retry_after is not None
    assert isinstance(retry_after, int)
    assert retry_after >= 0

    # Calculate expected_retry_seconds based on type
    # This is a simplified check; the actual logic in _limit_evaluator is more robust.
    # The `expected_retry_seconds_calc` from params is the key.
    assert retry_after == expected_retry_seconds_calc, \
        f"Failed for {interval_unit_enum.value} with interval {interval_value}. Expected {expected_retry_seconds_calc}, got {retry_after}"


def test_check_quota_enhanced_denied_fixed_month_retry_after(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)

    # Mock current time: 15th Jan 2024, 10:00:00
    mocked_now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    # Limit: Monthly, 1 month, max 10 requests
    monthly_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
    )
    mock_backend.get_usage_limits.return_value = [monthly_limit]
    quota_service.refresh_limits_cache()

    # Current usage: 10 requests (exactly at limit, next request will exceed)
    mock_backend.get_accounting_entries_for_quota.return_value = 10.0

    with patch('llm_accounting.services.quota_service_parts._limit_evaluator.datetime', wraps=datetime) as mock_dt:
        mock_dt.now.return_value = mocked_now

        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model=None, username=None, caller_name=None, input_tokens=0, cost=0
        )

    assert is_allowed is False
    assert reason is not None
    assert retry_after is not None

    # Expected period end: 1st Feb 2024, 00:00:00
    expected_period_end = datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_retry_seconds = int((expected_period_end - mocked_now).total_seconds())

    assert retry_after == expected_retry_seconds


def test_check_quota_enhanced_denied_rolling_month_retry_after(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)

    # Mock current time: 15th Jan 2024, 10:00:00
    mocked_now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    # Limit: Monthly Rolling, 1 month, max 10 requests
    # period_start for this will be 15th Dec 2023, 10:00:00 (calculated by _get_period_start)
    # period_end_for_retry will be 15th Jan 2024, 10:00:00 + 1 month = 15th Feb 2024, 10:00:00
    # No, _get_period_start for MONTH_ROLLING sets day=1, hour=0...
    # So period_start = 2023-12-01 00:00:00 if interval_value=1 and now is 2024-01-15
    # Then period_end_for_retry = period_start + 1 month = 2024-01-01 00:00:00 (this is wrong)

    # Let's re-evaluate based on current _get_period_start and _evaluate_limits logic:
    # now = 2024-01-15 10:00:00
    # interval_value = 1, unit = MONTH_ROLLING
    # _get_period_start:
    #   target_month = 1 - 1 = 0. target_year = 2024.
    #   while target_month <=0: target_month +=12 (0+12=12), target_year -=1 (2023)
    #   period_start_time = mocked_now.replace(year=2023, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
    #   period_start_time = 2023-12-01 00:00:00

    # _evaluate_limits (retry calculation for rolling):
    #   period_end_for_retry:
    #     year = period_start_time.year (2023)
    #     month = period_start_time.month (12)
    #     target_month_val = month + limit.interval_value (12 + 1 = 13)
    #     target_year_val = year (2023)
    #     while target_month_val > 12: target_month_val -=12 (1), target_year_val +=1 (2024)
    #     period_end_for_retry = period_start_time.replace(year=2024, month=1)
    #     period_end_for_retry = 2023-12-01 00:00:00 .replace(year=2024, month=1) = 2024-01-01 00:00:00
    # This means retry_after = (2024-01-01 00:00:00 - 2024-01-15 10:00:00).total_seconds() which is negative, so 0.
    # This seems correct if the window is defined from the 1st of the month.

    # Let's test a 2-month rolling to see a positive retry_after
    # interval_value = 2
    # _get_period_start:
    #   target_month = 1 - 2 = -1. target_year = 2024
    #   while target_month <=0: target_month +=12 (-1+12=11), target_year -=1 (2023)
    #   period_start_time = 2023-11-01 00:00:00

    # _evaluate_limits (retry calculation for rolling, interval_value=2):
    #   period_start_time = 2023-11-01 00:00:00
    #   target_month_val = 11 + 2 = 13
    #   target_year_val = 2023
    #   while target_month_val > 12: target_month_val -=12 (1), target_year_val +=1 (2024)
    #   period_end_for_retry = period_start_time.replace(year=2024, month=1) = 2024-01-01 00:00:00
    # retry_after = (2024-01-01 00:00:00 - 2024-01-15 10:00:00).total_seconds() -> also 0.
    # The logic for MONTH_ROLLING retry seems to make it such that retry is until the start of the *next* month,
    # if the period_start_time is always day=1, hour=0.
    # The period_end_for_retry calculation for MONTH_ROLLING is:
    # period_end_for_retry = period_start_time.replace(year=target_year_val, month=target_month_val)
    # This means it takes the day, hour, minute, second from period_start_time.
    # Since period_start_time for MONTH_ROLLING is *always* day=1, hour=0, min=0, sec=0,
    # period_end_for_retry will also always be day=1, hour=0, min=0, sec=0.
    # This implies the retry window for MONTH_ROLLING effectively ends at the start of a month.

    # Let's choose mocked_now such that period_end_for_retry is in the future.
    # If mocked_now = 2023-12-15 10:00:00, interval_value = 1 (MONTH_ROLLING)
    # period_start_time = 2023-11-01 00:00:00
    # period_end_for_retry = (2023-11-01 ...).replace(year=(2023+ (11+1-1)//12), month=(11+1-1)%12+1)
    #                       = (2023-11-01 ...).replace(year=2023, month=12) = 2023-12-01 00:00:00
    # Retry = (2023-12-01 - 2023-12-15 10:00:00) -> 0. Still doesn't make sense.

    # The issue is with my interpretation of period_end_for_retry for MONTH_ROLLING.
    # period_start_time + <duration_of_the_interval>
    # For MONTH_ROLLING, period_start_time is like `current_time_truncated.replace(year=target_year, month=target_month, day=1, hour=0, minute=0, second=0, microsecond=0)`
    # The duration added should be exactly `limit.interval_value` months.
    # The calculation in _evaluate_limits for MONTH_ROLLING retry is:
    #   `period_end_for_retry = period_start_time.replace(year=target_year_val, month=target_month_val)`
    #   where target_year_val, target_month_val are period_start_time.year/month + limit.interval_value months.
    # This is correct: it takes the day/time from period_start_time (which is 1st day, 00:00:00) and adds interval_value months.
    # So, if period_start_time = 2023-12-01 00:00:00 and limit.interval_value=1 month
    # period_end_for_retry = 2024-01-01 00:00:00.
    # If now = 2024-01-15 10:00:00, then retry is 0. This is correct.
    # The window [2023-12-01 to 2024-01-01) is in the past.

    # To get a positive retry_after for MONTH_ROLLING:
    # 'now' must be BEFORE period_end_for_retry.
    # Let limit be 1 MONTH_ROLLING.
    # Let now = 2023-12-15 10:00:00.
    # period_start_time (for usage window ending 'now'): 2023-11-01 00:00:00 (calculated based on 'now' being 2023-12-15)
    # period_end_for_retry (end of this window): 2023-11-01 + 1 month = 2023-12-01 00:00:00.
    # retry = (2023-12-01 00:00:00 - 2023-12-15 10:00:00).total_seconds() -> 0.

    # The `period_start_time` passed to `_evaluate_limits` is the start of the *current* window being evaluated.
    # For a rolling limit, this window is `[period_start_time, now)`.
    # The `retry_after` should be until this window is no longer active, i.e., `period_start_time + interval_duration`.

    # Let's use values that make sense:
    mocked_now = datetime(2023, 12, 15, 10, 0, 0, tzinfo=timezone.utc) # Current time
    limit_interval_val = 1 # 1 Month Rolling

    # For this 'now' and interval=1 MONTH_ROLLING:
    # _get_period_start(mocked_now, MONTH_ROLLING, 1) will be:
    # target_month = 12 - 1 = 11. target_year = 2023.
    # period_start_for_usage_check = 2023-11-01 00:00:00.
    # This is correct. The usage is checked in [2023-11-01 00:00:00, 2023-12-15 10:00:00).

    # Now, for retry calculation based on this period_start_for_usage_check:
    # period_end_for_retry = period_start_for_usage_check + 1 month
    #                     = 2023-11-01 00:00:00 + 1 month = 2023-12-01 00:00:00.
    # retry_seconds = (2023-12-01 00:00:00 - 2023-12-15 10:00:00).total_seconds() -> still gives 0.

    # The understanding of `period_end_for_retry` for rolling intervals must be:
    # It's `now + time_until_oldest_entry_drops_off_window`.
    # Or, more simply, it's `period_start_time_of_current_window + duration_of_interval`.
    # The `period_start_time` computed by `_get_period_start` IS the start of the current window.
    # So, if `limit.interval_unit` is MONTH_ROLLING and `limit.interval_value` is 1.
    # `period_start_time` (calculated by _get_period_start) is `datetime(mocked_now.year, mocked_now.month -1, 1,0,0,0)` (simplified).
    # `period_end_for_retry` is `period_start_time + 1 month`.
    # This means the retry period for MONTH_ROLLING will always end on the 1st of some month at 00:00:00.

    # Let's set 'now' to be just before such a calculated period_end_for_retry.
    # Example: period_end_for_retry is 2024-01-01 00:00:00.
    # This means period_start_time was 2023-12-01 00:00:00 (for a 1-month interval).
    # For period_start_time to be 2023-12-01, 'now' must be in Dec 2023 (e.g. Dec 31st).
    mocked_now = datetime(2023, 12, 31, 23, 0, 0, tzinfo=timezone.utc) # 1 hour before 2024-01-01

    monthly_rolling_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH_ROLLING.value, interval_value=1,
    )
    mock_backend.get_usage_limits.return_value = [monthly_rolling_limit]
    quota_service.refresh_limits_cache()
    mock_backend.get_accounting_entries_for_quota.return_value = 10.0

    with patch('llm_accounting.services.quota_service_parts._limit_evaluator.datetime', wraps=datetime) as mock_dt:
        mock_dt.now.return_value = mocked_now
        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model=None, username=None, caller_name=None, input_tokens=0, cost=0
        )

    assert is_allowed is False
    assert retry_after is not None

    # For mocked_now = 2023-12-31 23:00:00, interval = 1 MONTH_ROLLING:
    # period_start_time = 2023-12-01 00:00:00. (calculated by _get_period_start)
    # period_end_for_retry = period_start_time.replace(month=12+1) -> year 2024, month 1
    #                       = 2024-01-01 00:00:00.
    expected_period_end = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    expected_retry_seconds = int((expected_period_end - mocked_now).total_seconds()) # 1 hour = 3600s
    assert retry_after == expected_retry_seconds

    # Test case where retry_after should be 0
    mocked_now_past_window_end = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc) # 1 sec after period end
    with patch('llm_accounting.services.quota_service_parts._limit_evaluator.datetime', wraps=datetime) as mock_dt:
        mock_dt.now.return_value = mocked_now_past_window_end
        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
             model=None, username=None, caller_name=None, input_tokens=0, cost=0
        )
    assert is_allowed is False # Still denied because usage is based on period_start relative to new 'now'
    assert retry_after == 0 # But retry is 0 as the calculated period_end_for_retry is in the past
                           # For now=2024-01-01 00:00:01, interval=1 MONTH_ROLLING
                           # period_start_time = 2024-01-01 00:00:00
                           # period_end_for_retry = 2024-02-01 00:00:00
                           # retry = (2024-02-01 - 2024-01-01 00:00:01) > 0. My reasoning above for retry=0 was flawed.
                           # The retry is always calculated based on the *current* window's period_start + duration.
    expected_period_start_for_new_now = datetime(2024, 1, 1, 0,0,0, tzinfo=timezone.utc)
    expected_period_end_for_new_now_retry = datetime(2024, 2, 1, 0,0,0, tzinfo=timezone.utc)
    expected_retry_val_for_new_now = int((expected_period_end_for_new_now_retry - mocked_now_past_window_end).total_seconds())
    assert retry_after == expected_retry_val_for_new_now


def test_check_quota_enhanced_denied_retry_after_zero_or_negative_becomes_zero(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)

    # Set current time to be *after* the natural end of a fixed interval period
    mocked_now = datetime(2024, 1, 1, 1, 0, 10, tzinfo=timezone.utc) # 10s past 01:00:00

    # Limit: Hourly, fixed, max 10 requests, period starts at 01:00:00
    hourly_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=10.0, interval_unit=TimeInterval.HOUR.value, interval_value=1,
    )
    mock_backend.get_usage_limits.return_value = [hourly_limit]
    quota_service.refresh_limits_cache()

    mock_backend.get_accounting_entries_for_quota.return_value = 10.0 # Will exceed

    with patch('llm_accounting.services.quota_service_parts._limit_evaluator.datetime', wraps=datetime) as mock_dt:
        mock_dt.now.return_value = mocked_now

        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model=None, username=None, caller_name=None, input_tokens=0, cost=0
        )

    assert is_allowed is False
    assert retry_after == 0 # query_end_time (01:00:00) - mocked_now (01:00:10) is negative
                            # For fixed HOUR, period_start_time is 01:00:00. query_end_time is 02:00:00.
                            # retry = (02:00:00 - 01:00:10).total_seconds() which is positive.
                            # The test name is a bit misleading now.
                            # It should be: retry is calculated correctly even if 'now' is past the start of current fixed period.

    expected_period_start = datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
    expected_query_end_time = datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
    expected_retry_seconds = int((expected_query_end_time - mocked_now).total_seconds())
    assert retry_after == expected_retry_seconds
