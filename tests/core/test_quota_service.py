from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call # Added call
import pytest
from typing import Optional # Added Optional

# Updated import: UsageLimit changed to UsageLimitData
# Also importing enums needed for creating UsageLimitData instances
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval, # Added TimeInterval
                                          UsageLimitDTO)
from llm_accounting.services.quota_service import QuotaService
from llm_accounting.backends.base import BaseBackend # For type hinting the mock_backend


# Fixture for a mock backend, as QuotaService depends on a backend instance
@pytest.fixture
def mock_backend() -> MagicMock:
    """Provides a MagicMock instance for BaseBackend."""
    backend = MagicMock(spec=BaseBackend)
    # Default to returning no limits for initial load, tests can override this
    backend.get_usage_limits.return_value = []
    return backend

# Removed the general quota_service fixture, as most tests will need to
# instantiate QuotaService after setting mock_backend.get_usage_limits.return_value

def test_check_quota_no_limits(mock_backend: MagicMock):
    """Test check_quota when no limits are configured (cache is empty)."""
    # mock_backend.get_usage_limits.return_value is already [] from fixture
    quota_service = QuotaService(mock_backend) # Cache loaded here

    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01
    )
    
    assert is_allowed is True
    assert reason is None
    # get_usage_limits is called once during QuotaService initialization
    mock_backend.get_usage_limits.assert_called_once()


def test_check_quota_allowed_single_limit(mock_backend: MagicMock):
    """Test check_quota when usage is within a single configured limit."""
    now = datetime.now(timezone.utc)
    user_cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    # Set up the backend mock for initial cache loading
    mock_backend.get_usage_limits.return_value = [user_cost_limit]
    quota_service = QuotaService(mock_backend)

    # Current usage for the period (e.g., $5 for the month)
    mock_backend.get_accounting_entries_for_quota.return_value = 5.0 
    
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller", # This request matches the user_cost_limit
        input_tokens=100, cost=0.01 # Request cost is $0.01
    )
    
    assert is_allowed is True
    assert reason is None

    # Verify that get_usage_limits was called once for cache loading
    mock_backend.get_usage_limits.assert_called_once()
    
    # Verify that get_accounting_entries_for_quota was called ONCE for the USER limit
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

    # Current usage for the period (e.g., $9.99 for the month)
    mock_backend.get_accounting_entries_for_quota.return_value = 9.99
    
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=0, cost=0.02 # Request cost is $0.02, total would be $10.01
    )
    
    assert is_allowed is False
    assert reason is not None
    assert "USER (user: test_user) limit: 10.00 cost per 1 month" in reason
    assert "current usage: 9.99, request: 0.02" in reason

    mock_backend.get_usage_limits.assert_called_once() # Called during init
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
    # Cache will contain both limits for "test_user"
    mock_backend.get_usage_limits.return_value = [cost_limit_user, request_limit_user]
    quota_service = QuotaService(mock_backend)

    # Scenario: Cost is fine, but requests are exceeded
    def get_accounting_side_effect(start_time, limit_type, model, username, caller_name, project_name, filter_project_null):
        # This side effect will be called by _evaluate_limits for each relevant limit in the cache
        if limit_type == LimitType.COST and username == "test_user":
            return 5.0 # Well within $10 cost limit
        elif limit_type == LimitType.REQUESTS and username == "test_user":
            return 100.0 # Already at 100 requests, next one (count as 1) will exceed
        return 0.0
    
    mock_backend.get_accounting_entries_for_quota.side_effect = get_accounting_side_effect
    
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=10, cost=0.01 # Request cost is $0.01, request count is 1
    )
    
    assert is_allowed is False
    assert reason is not None
    # The failure message will be for the first limit that's hit based on QuotaService's internal check order
    # and how limits are ordered in the cache, if that influences _evaluate_limits.
    # Assuming request_limit_user is evaluated and hit.
    assert "USER (user: test_user) limit: 100.00 requests per 1 day" in reason
    assert "current usage: 100.00, request: 1.00" in reason

    mock_backend.get_usage_limits.assert_called_once() # Init
    # get_accounting_entries_for_quota will be called for COST limit (passes) and then for REQUESTS limit (fails)
    # The order depends on the iteration order of limits in _evaluate_limits if they are of the same scope.
    # And the order of checks in check_quota (global, model, project, user etc.)
    # For user scope, both limits apply.
    assert mock_backend.get_accounting_entries_for_quota.call_count == 2


def test_check_quota_different_scopes_in_cache(mock_backend: MagicMock):
    """Test that QuotaService correctly filters from cache for different scopes."""
    now = datetime.now(timezone.utc)
    global_req_limit = UsageLimitDTO(id=1, scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value, max_value=5, interval_unit=TimeInterval.MINUTE.value, interval_value=1)
    user_cost_limit = UsageLimitDTO(id=2, scope=LimitScope.USER.value, username="test_user", limit_type=LimitType.COST.value, max_value=10, interval_unit=TimeInterval.DAY.value, interval_value=1)
    model_token_limit = UsageLimitDTO(id=3, scope=LimitScope.MODEL.value, model="gpt-4", limit_type=LimitType.INPUT_TOKENS.value, max_value=1000, interval_unit=TimeInterval.HOUR.value, interval_value=1)
    
    mock_backend.get_usage_limits.return_value = [global_req_limit, user_cost_limit, model_token_limit]
    quota_service = QuotaService(mock_backend)
    
    # Scenario: Global limit is hit first
    mock_backend.get_accounting_entries_for_quota.return_value = 5.0 # Signifying 5 requests already made globally

    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="super_caller",
        input_tokens=1, cost=0.001
    )
    
    assert not is_allowed
    assert "GLOBAL limit: 5.00 requests per 1 minute" in reason

    mock_backend.get_usage_limits.assert_called_once() # Init
    # Only get_accounting_entries_for_quota for the global limit should be called as it's checked first and denies
    mock_backend.get_accounting_entries_for_quota.assert_called_once()
    assert mock_backend.get_accounting_entries_for_quota.call_args.kwargs['limit_type'] == LimitType.REQUESTS
    # For global limit, specific entity fields should be None in get_accounting_entries_for_quota call
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
    # Only this limit will be in cache
    mock_backend.get_usage_limits.return_value = [model_token_limit]
    quota_service = QuotaService(mock_backend)

    mock_backend.get_accounting_entries_for_quota.return_value = 950.0 # 950 tokens used this hour for this model

    # Scenario 1: Allowed
    is_allowed, reason = quota_service.check_quota(
        model="text-davinci-003", username="any_user", caller_name="any_caller",
        input_tokens=50, cost=0.0 # 50 tokens requested
    )
    assert is_allowed is True
    assert reason is None
    mock_backend.get_accounting_entries_for_quota.assert_called_with(
        start_time=mock_backend.get_accounting_entries_for_quota.call_args.kwargs['start_time'], # Keep dynamic start_time
        limit_type=LimitType.INPUT_TOKENS,
        model="text-davinci-003", # Model from limit
        username=None, caller_name=None, project_name=None, filter_project_null=None
    )


    # Scenario 2: Denied
    mock_backend.get_accounting_entries_for_quota.reset_mock() # Reset from previous call
    mock_backend.get_accounting_entries_for_quota.return_value = 950.0 # Set again for this check

    is_allowed, reason = quota_service.check_quota(
        model="text-davinci-003", username="any_user", caller_name="any_caller",
        input_tokens=51, cost=0.0 # 51 tokens requested, total 1001, limit 1000
    )
    assert is_allowed is False
    assert reason is not None
    assert "MODEL (model: text-davinci-003) limit: 1000.00 input_tokens per 1 hour" in reason
    assert "current usage: 950.00, request: 51.00" in reason

    mock_backend.get_usage_limits.assert_called_once() # Called during init
    # get_accounting_entries_for_quota called once for allowed, once for denied
    assert mock_backend.get_accounting_entries_for_quota.call_count == 1 # Called once for this specific check_quota call


def test_get_period_start_monthly(mock_backend: MagicMock): # Added mock_backend for consistency, though not used
    quota_service = QuotaService(mock_backend) # Instantiated here for _get_period_start tests
    """Test _get_period_start for monthly interval."""
    # Test for a specific date
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service._get_period_start(current_time, TimeInterval.MONTH, 1)
    assert period_start == datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Test for beginning of month
    current_time = datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    period_start = quota_service._get_period_start(current_time, TimeInterval.MONTH, 1)
    assert period_start == datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_daily(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    """Test _get_period_start for daily interval."""
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service._get_period_start(current_time, TimeInterval.DAY, 1)
    assert period_start == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_hourly(mock_backend: MagicMock):
    quota_service = QuotaService(mock_backend)
    """Test _get_period_start for hourly interval."""
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service._get_period_start(current_time, TimeInterval.HOUR, 1)
    assert period_start == datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

# More tests could be added for other intervals (WEEK, MINUTE, SECOND) and different interval_value
# and for cases where TimeInterval.MONTH.value is "monthly" string vs TimeInterval.MONTH enum.
# The QuotaService._get_period_start seems to handle enum directly.
# The UsageLimitData stores interval_unit as string. QuotaService should handle this.
# In check_quota, limit.interval_unit (string) is converted to TimeInterval enum.
# This seems fine.
