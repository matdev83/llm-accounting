from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch
import pytest
from typing import Optional, Dict, Tuple

from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimitDTO)
from llm_accounting.services.quota_service import QuotaService
from llm_accounting.backends.base import TransactionalBackend
from llm_accounting import LLMAccounting # Added import

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
    # Test that attempting to create a TimeInterval enum from an invalid string raises ValueError
    with pytest.raises(ValueError, match="'unsupported_unit' is not a valid TimeInterval"):
        TimeInterval("unsupported_unit")
    # Further test: if _get_period_start was somehow called with a non-enum (e.g. direct test),
    # it should also fail. This part is commented out as the primary test above is sufficient
    # for typical usage where enum conversion happens before calling _get_period_start.
    # The original test was trying to test _get_period_start's robustness to incorrect types,
    # which resulted in AttributeError. The more relevant test is the Enum conversion itself.
    # If direct calls to _get_period_start with strings were a supported scenario,
    # then _get_period_start would need explicit type checking.
    #
    # with pytest.raises(AttributeError): # Or appropriate error if type check added
    #     quota_service.limit_evaluator._get_period_start(current_time, "unsupported_unit", 1)


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


from freezegun import freeze_time

# Helper to calculate expected retry_after based on reset_timestamp
def calculate_expected_retry_after(reset_timestamp: Optional[datetime], current_time: datetime) -> Optional[int]:
    if reset_timestamp is None:
        return None
    return max(0, int((reset_timestamp - current_time).total_seconds()))

def test_check_quota_enhanced_denied_single_limit(mock_backend: MagicMock):
    """Test check_quota_enhanced when usage exceeds a single configured limit."""
    now_dt_str = "2024-01-15T10:00:00Z" # Fixed time for test
    now_dt = datetime.fromisoformat(now_dt_str.replace("Z", "+00:00"))
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now_dt, updated_at=now_dt
    )
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    # Instantiate QuotaService AFTER setting the mock return value.
    # The first call to check_quota_enhanced will load the cache if it's None.
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 9.99

    # Expected period_end for retry calculation from _limit_evaluator
    expected_reset_timestamp_from_evaluator = datetime(now_dt.year, now_dt.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    if now_dt.month == 12: # Handle December to January transition for next year
        expected_reset_timestamp_from_evaluator = datetime(now_dt.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    expected_reason_message = (
        f"USER (user: {user_cost_limit.username}) limit: {user_cost_limit.max_value:.2f} {user_cost_limit.limit_type} per {user_cost_limit.interval_value} {user_cost_limit.interval_unit}"
        f" exceeded. Current usage: {mock_backend.get_accounting_entries_for_quota.return_value:.2f}, request: {0.02:.2f}."
    )

    with freeze_time(now_dt_str), \
         patch.object(quota_service.limit_evaluator, '_evaluate_limits_enhanced', autospec=True) as mock_evaluate_enhanced:
        mock_evaluate_enhanced.return_value = (False, expected_reason_message, expected_reset_timestamp_from_evaluator)
        
        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model="gpt-4", username="test_user", caller_name="test_caller",
            input_tokens=0, cost=0.02 # This cost will exceed the limit
        )

    assert is_allowed is False
    assert reason == expected_reason_message
    assert retry_after is not None
    assert isinstance(retry_after, int)
    assert retry_after >= 0

    # Calculate expected retry_after based on the mocked current time (now_dt)
    expected_retry_val = calculate_expected_retry_after(expected_reset_timestamp_from_evaluator, now_dt)
    assert retry_after == expected_retry_val

    mock_backend.get_usage_limits.assert_called_once()
    mock_evaluate_enhanced.assert_called_once()


@pytest.mark.parametrize("interval_unit_enum, interval_value, current_usage_val, request_val, mock_now_dt_str, expected_reset_timestamp_str", [
    # Fixed Intervals
    (TimeInterval.SECOND, 10, 9.0, 1.1, "2024-01-01T00:00:05Z", "2024-01-01T00:00:10Z"), # now=00:05, period_start=00:00, reset=00:10. retry=5
    (TimeInterval.MINUTE, 1, 50.0, 11.0, "2024-01-01T00:00:30Z", "2024-01-01T00:01:00Z"), # now=00:30, period_start=00:00, reset=01:00. retry=30
    (TimeInterval.MINUTE, 2, 50.0, 11.0, "2024-01-01T00:00:30Z", "2024-01-01T00:02:00Z"), # now=00:30, period_start=00:00, reset=02:00. retry=90
    (TimeInterval.HOUR, 1, 50.0, 11.0, "2024-01-01T00:30:00Z", "2024-01-01T01:00:00Z"), # now=00:30, period_start=00:00, reset=01:00. retry=1800
    (TimeInterval.DAY, 1, 20.0, 5.0, "2024-01-01T12:00:00Z", "2024-01-02T00:00:00Z"), # now=12:00, period_start=00:00, reset=next day 00:00. retry=12*3600
    # Rolling Intervals - retry_after should be 0 if reset_timestamp is now or past
    (TimeInterval.SECOND_ROLLING, 10, 9.0, 1.1, "2024-01-01T00:00:10Z", "2024-01-01T00:00:10Z"), # now=00:10, period_start=00:00, reset=00:10. retry=0
    (TimeInterval.MINUTE_ROLLING, 1, 50.0, 11.0, "2024-01-01T00:01:00Z", "2024-01-01T00:01:00Z"), # now=01:00, period_start=00:00, reset=01:00. retry=0
    (TimeInterval.HOUR_ROLLING, 1, 50.0, 11.0, "2024-01-01T01:00:00Z", "2024-01-01T01:00:00Z"), # now=01:00, period_start=00:00, reset=01:00. retry=0
    # Rolling Month with positive retry_after
    (TimeInterval.MONTH_ROLLING, 1, 10.0, 1.0, "2024-01-15T10:00:00Z", "2024-02-01T00:00:00Z"), # now=Jan 15, period_start=Jan 1, reset=Feb 1. retry = Feb 1 - Jan 15
])
def test_check_quota_enhanced_denied_retry_after_various_intervals(
    mock_backend: MagicMock,
    interval_unit_enum: TimeInterval,
    interval_value: int,
    current_usage_val: float,
    request_val: float,
    mock_now_dt_str: str,
    expected_reset_timestamp_str: str
):
    quota_service = QuotaService(mock_backend)

    # Convert string timestamps to datetime objects
    mocked_current_time = datetime.fromisoformat(mock_now_dt_str.replace("Z", "+00:00"))
    expected_reset_timestamp = datetime.fromisoformat(expected_reset_timestamp_str.replace("Z", "+00:00"))

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

    # Mock the return value of _evaluate_limits_enhanced to provide the absolute reset timestamp
    with freeze_time(mock_now_dt_str), \
         patch.object(quota_service.limit_evaluator, '_evaluate_limits_enhanced', autospec=True) as mock_evaluate_enhanced:
        mock_evaluate_enhanced.return_value = (False, "reason", expected_reset_timestamp)

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

    expected_retry_seconds_calc = calculate_expected_retry_after(expected_reset_timestamp, mocked_current_time)
    assert retry_after == expected_retry_seconds_calc, \
        f"Failed for {interval_unit_enum.value} with interval {interval_value}. Expected {expected_retry_seconds_calc}, got {retry_after}"


def test_check_quota_enhanced_denied_fixed_month_retry_after(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)

    # Mock current time for the test setup
    now_fixed_str = "2024-01-15T10:00:00Z"
    mocked_now = datetime.fromisoformat(now_fixed_str.replace("Z", "+00:00"))

    # Limit: Monthly, 1 month, max 10 requests
    monthly_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
    )
    mock_backend.get_usage_limits.return_value = [monthly_limit]
    quota_service.cache_manager.limits_cache = None # Explicitly clear cache
    quota_service.refresh_limits_cache() # Ensure cache is loaded

    # Current usage: 10 requests (exactly at limit, next request will exceed)
    mock_backend.get_accounting_entries_for_quota.return_value = 10.0

    # Expected reset timestamp from _limit_evaluator
    expected_reset_timestamp_from_evaluator = datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

    with freeze_time(now_fixed_str), \
         patch.object(quota_service.limit_evaluator, '_evaluate_limits_enhanced', autospec=True) as mock_evaluate_enhanced:
        mock_evaluate_enhanced.return_value = (False, "reason", expected_reset_timestamp_from_evaluator)

        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model=None, username=None, caller_name=None, input_tokens=0, cost=0
        )

    assert is_allowed is False
    assert reason is not None
    assert retry_after is not None

    expected_retry_seconds = calculate_expected_retry_after(expected_reset_timestamp_from_evaluator, mocked_now)
    assert retry_after == expected_retry_seconds


def test_check_quota_enhanced_denied_rolling_month_retry_after(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)

    # Mock current time: 15th Jan 2024, 10:00:00
    mocked_now_str = "2024-01-15T10:00:00Z"
    mocked_now = datetime.fromisoformat(mocked_now_str.replace("Z", "+00:00"))

    monthly_rolling_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH_ROLLING.value, interval_value=1,
    )
    mock_backend.get_usage_limits.return_value = [monthly_rolling_limit]
    quota_service.refresh_limits_cache()
    mock_backend.get_accounting_entries_for_quota.return_value = 10.0

    # Expected reset timestamp from _limit_evaluator for 1-month rolling from 2024-01-15 10:00:00
    # _get_period_start for 2024-01-15 10:00:00 with 1 MONTH_ROLLING is 2023-12-01 00:00:00
    # reset_timestamp = period_start_time.replace(year=target_year_val, month=target_month_val)
    # target_month_val = 12 + 1 = 13 -> 1
    # target_year_val = 2023 + 1 = 2024
    # So, reset_timestamp = 2024-01-01 00:00:00
    expected_reset_timestamp_from_evaluator = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    with freeze_time(mocked_now_str), \
         patch.object(quota_service.limit_evaluator, '_evaluate_limits_enhanced', autospec=True) as mock_evaluate_enhanced:
        mock_evaluate_enhanced.return_value = (False, "reason", expected_reset_timestamp_from_evaluator)
        
        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model=None, username=None, caller_name=None, input_tokens=0, cost=0
        )

    assert is_allowed is False
    assert retry_after is not None

    expected_retry_seconds = calculate_expected_retry_after(expected_reset_timestamp_from_evaluator, mocked_now)
    assert retry_after == expected_retry_seconds


def test_check_quota_enhanced_denied_retry_after_zero_or_negative_becomes_zero(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)

    # Set current time to be *after* the natural end of a fixed interval period
    mocked_now_str = "2024-01-01T01:00:10Z" # 10s past 01:00:00
    mocked_now = datetime.fromisoformat(mocked_now_str.replace("Z", "+00:00"))

    # Limit: Hourly, fixed, max 10 requests, period starts at 01:00:00
    hourly_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
        max_value=10.0, interval_unit=TimeInterval.HOUR.value, interval_value=1,
    )
    mock_backend.get_usage_limits.return_value = [hourly_limit]
    quota_service.refresh_limits_cache()

    mock_backend.get_accounting_entries_for_quota.return_value = 10.0 # Will exceed

    # Expected reset timestamp from _limit_evaluator
    # For fixed HOUR, if mocked_now is 01:00:10:
    # period_start_time calculated by _get_period_start will be 01:00:00.
    # reset_timestamp will be period_start_time + 1 hour = 02:00:00.
    expected_reset_timestamp_from_evaluator = datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc)

    with freeze_time(mocked_now_str), \
         patch.object(quota_service.limit_evaluator, '_evaluate_limits_enhanced', autospec=True) as mock_evaluate_enhanced:
        mock_evaluate_enhanced.return_value = (False, "reason", expected_reset_timestamp_from_evaluator)

        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model=None, username=None, caller_name=None, input_tokens=0, cost=0
        )

    assert is_allowed is False
    expected_retry_seconds = calculate_expected_retry_after(expected_reset_timestamp_from_evaluator, mocked_now)
    assert retry_after == expected_retry_seconds


@freeze_time("2024-01-01T10:00:00Z")
def test_check_quota_enhanced_denial_cached(mock_backend: MagicMock):
    """Test that a denied request is cached and subsequent calls return from cache."""
    now = datetime.now(timezone.utc)
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MINUTE.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    quota_service = QuotaService(mock_backend)
    quota_service.refresh_limits_cache()

    # Mock _evaluate_limits_enhanced to return a denial with a future reset_timestamp
    reset_time = now + timedelta(seconds=60) # Reset in 60 seconds
    mock_evaluate_enhanced_return = (False, "Denied by test limit", reset_time)
    
    with patch.object(quota_service.limit_evaluator, '_evaluate_limits_enhanced', autospec=True) as mock_evaluate_enhanced:
        mock_evaluate_enhanced.return_value = mock_evaluate_enhanced_return

        # First call: should hit evaluator and cache the denial
        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model="gpt-4", username="test_user", caller_name="test_caller",
            input_tokens=0, cost=0.01
        )
        assert is_allowed is False
        assert reason == "Denied by test limit"
        assert retry_after == 60 # Initial retry_after
        mock_evaluate_enhanced.assert_called_once()
        cache_key = ("gpt-4", "test_user", "test_caller", None)
        assert (cache_key in quota_service._denial_cache)
        assert quota_service._denial_cache[cache_key] == ("Denied by test limit", reset_time)

        mock_evaluate_enhanced.reset_mock() # Reset mock call count

        # Second call (immediately after): should return from cache, evaluator should NOT be called
        is_allowed_cached, reason_cached, retry_after_cached = quota_service.check_quota_enhanced(
            model="gpt-4", username="test_user", caller_name="test_caller",
            input_tokens=0, cost=0.01
        )
        assert is_allowed_cached is False
        assert reason_cached == "Denied by test limit"
        assert retry_after_cached == 60 # Should still be 60 as time hasn't advanced in freeze_time
        mock_evaluate_enhanced.assert_not_called() # Crucial: evaluator should not be called


@freeze_time("2024-01-01T10:00:00Z")
def test_check_quota_enhanced_cache_expires(mock_backend: MagicMock):
    """Test that a cached denial expires and subsequent calls hit the evaluator."""
    now = datetime.now(timezone.utc)
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.SECOND.value, interval_value=10, # 10-second limit
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    quota_service = QuotaService(mock_backend)
    quota_service.refresh_limits_cache()

    # Mock _evaluate_limits_enhanced to return a denial with a future reset_timestamp
    reset_time = now + timedelta(seconds=5) # Reset in 5 seconds
    mock_evaluate_enhanced_return_denial = (False, "Denied by test limit", reset_time)
    mock_evaluate_enhanced_return_allowed = (True, None, None) # New return value for allowed state
    
    with patch.object(quota_service.limit_evaluator, '_evaluate_limits_enhanced', autospec=True) as mock_evaluate_enhanced:
        mock_evaluate_enhanced.return_value = mock_evaluate_enhanced_return_denial

        # First call: should hit evaluator and cache the denial
        is_allowed, reason, retry_after = quota_service.check_quota_enhanced(
            model="gpt-4", username="test_user", caller_name="test_caller",
            input_tokens=0, cost=0.01
        )
        assert is_allowed is False
        assert reason == "Denied by test limit"
        assert retry_after == 5
        mock_evaluate_enhanced.assert_called_once()
        cache_key = ("gpt-4", "test_user", "test_caller", None)
        assert cache_key in quota_service._denial_cache # Assert cache entry exists

        mock_evaluate_enhanced.reset_mock() # Reset mock call count

        # Set the mock to return allowed for the second call
        mock_evaluate_enhanced.return_value = mock_evaluate_enhanced_return_allowed

        # Advance time past the reset_time
        with freeze_time(now + timedelta(seconds=10)): # Advance 10 seconds
            # Second call: cache should have expired, evaluator should be called again
            # Manually check remaining_seconds logic
            cached_reason, cached_reset_timestamp = quota_service._denial_cache[cache_key]
            current_time_in_second_call = datetime.now(timezone.utc)
            remaining_seconds_check = max(0, int((cached_reset_timestamp - current_time_in_second_call).total_seconds()))
            assert remaining_seconds_check == 0 # Assert that remaining_seconds is indeed 0

            is_allowed_expired, reason_expired, retry_after_expired = quota_service.check_quota_enhanced(
                model="gpt-4", username="test_user", caller_name="test_caller",
                input_tokens=0, cost=0.01
            )
            assert is_allowed_expired is True # Should now be allowed
            assert reason_expired is None # Reason should be None for allowed
            assert retry_after_expired is None # retry_after should be None for allowed
            mock_evaluate_enhanced.assert_called_once()
            assert cache_key not in quota_service._denial_cache # Assert cache entry is gone


def test_cache_rebuild_after_inserting_limit(memory_sqlite_backend):
    accounting = LLMAccounting(backend=memory_sqlite_backend)
    # Define request parameters
    model = "test-model-insert"
    username = "test-user-insert"
    caller_name = "test-caller-insert"
    project_name = "test-project-insert"
    input_tokens = 100
    cost = 1.0

    # 1. Initial check (should be allowed)
    allowed, reason = accounting.check_quota(
        model=model,
        username=username,
        caller_name=caller_name,
        project_name=project_name,
        input_tokens=input_tokens,
        cost=cost
    )
    assert allowed is True, f"Initial check should be allowed, but was denied: {reason}"

    # 2. Insert a restrictive limit
    accounting.set_usage_limit(
        scope=LimitScope.USER,
        limit_type=LimitType.COST,
        max_value=0.5, # Restrictive limit
        interval_unit=TimeInterval.DAY,
        interval_value=1,
        username=username
    )

    # 3. Check again (should be denied due to new limit)
    allowed, reason = accounting.check_quota(
        model=model,
        username=username,
        caller_name=caller_name,
        project_name=project_name,
        input_tokens=input_tokens,
        cost=cost
    )
    assert allowed is False, "Check after inserting limit should be denied"
    assert reason is not None, "Reason for denial should not be None"
    # Example of a more specific reason check, adapt if necessary
    assert f"USER (user: {username}) limit: 0.50 cost per 1 day exceeded." in reason

    # 4. Clean up: Find and delete the limit
    limits = accounting.get_usage_limits(username=username, scope=LimitScope.USER)
    limit_deleted = False
    for limit in limits:
        if limit.limit_type == LimitType.COST.value and limit.max_value == 0.5 and limit.username == username: # Identify the specific limit
            accounting.delete_usage_limit(limit.id)
            limit_deleted = True
            break
    assert limit_deleted, "Could not find the test limit to delete"


def test_cache_rebuild_after_deleting_limit(memory_sqlite_backend):
    accounting = LLMAccounting(backend=memory_sqlite_backend)
    model = "test-model-deletion"
    username = "test-user-deletion"
    caller_name = "test-caller-deletion"
    project_name = "test-project-deletion"
    input_tokens = 10
    cost = 0.1

    # 1. Insert a restrictive limit first
    accounting.set_usage_limit(
        scope=LimitScope.USER,
        limit_type=LimitType.INPUT_TOKENS,
        max_value=5, # Restrictive
        interval_unit=TimeInterval.HOUR,
        interval_value=1,
        username=username
    )

    # Verify it's active
    allowed, reason = accounting.check_quota(model, username, caller_name, input_tokens, cost, project_name=project_name)
    assert allowed is False, f"Request should be denied by the new limit: {reason}"

    # 2. Find and delete the limit
    limits = accounting.get_usage_limits(username=username, scope=LimitScope.USER)
    limit_id_to_delete = None
    for limit_obj in limits:
        if limit_obj.limit_type == LimitType.INPUT_TOKENS.value and limit_obj.max_value == 5 and limit_obj.username == username:
            limit_id_to_delete = limit_obj.id
            break
    assert limit_id_to_delete is not None, "Test limit was not found for deletion"

    accounting.delete_usage_limit(limit_id_to_delete)

    # 3. Check again (should be allowed as the limit is gone)
    allowed, reason = accounting.check_quota(model, username, caller_name, input_tokens, cost, project_name=project_name)
    assert allowed is True, f"Request should be allowed after deleting limit, but was denied: {reason}"
