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
    return backend

@pytest.fixture
def quota_service(mock_backend: MagicMock) -> QuotaService:
    """Provides a QuotaService instance initialized with a mock backend."""
    return QuotaService(mock_backend)


def test_check_quota_no_limits(quota_service: QuotaService, mock_backend: MagicMock):
    """Test check_quota when no limits are configured."""
    mock_backend.get_usage_limits.return_value = []
    
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01
    )
    
    assert is_allowed is True
    assert reason is None
    # Check that get_usage_limits was called multiple times (e.g., 5 times for the different scopes)
    # and that for each call, the appropriate parameters were used.
    # The exact number of calls might change if QuotaService logic changes.
    # Based on current QuotaService structure: MODEL, GLOBAL, USER, CALLER (general), CALLER (user+caller)
    assert mock_backend.get_usage_limits.call_count >= 1 # At least one call for GLOBAL if others are specific
    
    expected_calls = [
        call(scope=LimitScope.MODEL, model="gpt-4"),
        call(scope=LimitScope.GLOBAL),
        call(scope=LimitScope.USER, username="test_user"),
        call(scope=LimitScope.CALLER, caller_name="test_caller"), # General caller
        call(scope=LimitScope.CALLER, username="test_user", caller_name="test_caller") # User+Caller
    ]
    # Use any_order=True because the internal order of fetching these specific scopes might not be guaranteed
    # or strictly necessary for this test's purpose if all return empty.
    # However, QuotaService has a defined order of checks. Let's assume that for "no limits",
    # it will try all relevant specific scopes.
    # A simpler check might be to just ensure call_count is as expected (e.g., 5)
    # and that it's called with variations of the input parameters.
    # For this test, the main point is that it eventually returns True because all calls yield no limits.
    # So, just checking call_count might be sufficient if we trust other tests to verify specific call args.
    assert mock_backend.get_usage_limits.call_count == 5 # Based on the 5 checks in QuotaService


def test_check_quota_allowed_single_limit(quota_service: QuotaService, mock_backend: MagicMock):
    """Test check_quota when usage is within a single configured limit."""
    now = datetime.now(timezone.utc)
    limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [limit]
    # Current usage for the period (e.g., $5 for the month)
    mock_backend.get_accounting_entries_for_quota.return_value = 5.0 
    
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01 # Request cost is $0.01
    )
    
    assert is_allowed is True
    assert reason is None

    # Define a side_effect function for mock_backend.get_usage_limits
    # This function will be called each time mock_backend.get_usage_limits is invoked
    def get_usage_limits_side_effect(scope: Optional[LimitScope] = None, model: Optional[str] = None, 
                                     username: Optional[str] = None, caller_name: Optional[str] = None, 
                                     project_name: Optional[str] = None, filter_project_null: Optional[bool] = None,
                                     filter_username_null: Optional[bool] = None, filter_caller_name_null: Optional[bool] = None):
        # Only return the 'limit' if the scope and username match the specific USER limit we're testing
        if scope == LimitScope.USER and username == "test_user":
            return [limit] 
        return [] # For all other calls (MODEL, GLOBAL, CALLER scopes), return no limits

    mock_backend.get_usage_limits.side_effect = get_usage_limits_side_effect
    
    # Reset mocks if they were called during initial setup of side_effect (though not strictly necessary here)
    # mock_backend.get_usage_limits.reset_mock() # Not needed as it's fresh for this test logic
    mock_backend.get_accounting_entries_for_quota.reset_mock() # Reset this as it's called by check_quota

    # Re-run check_quota with the new side_effect in place for get_usage_limits
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=100, cost=0.01 # Request cost is $0.01
    )
    
    assert is_allowed is True # Should still be allowed
    assert reason is None

    # Verify that get_usage_limits was called for the USER scope with correct parameters
    # (among other calls QuotaService makes)
    mock_backend.get_usage_limits.assert_any_call(scope=LimitScope.USER, username="test_user")
    
    # Verify that get_accounting_entries_for_quota was called ONCE, 
    # specifically for the USER limit that was found and evaluated.
    mock_backend.get_accounting_entries_for_quota.assert_called_once()
    # Correctly access keyword arguments
    kwargs = mock_backend.get_accounting_entries_for_quota.call_args.kwargs
    assert kwargs['limit_type'] == LimitType.COST # limit_type argument from the 'limit' object
    # The username passed to get_accounting_entries_for_quota should be the one from the limit object
    # if the limit is user-specific.
    assert kwargs['username'] == "test_user"    # username argument (from the limit's scope)

def test_check_quota_denied_single_limit(quota_service: QuotaService, mock_backend: MagicMock):
    """Test check_quota when usage exceeds a single configured limit."""
    now = datetime.now(timezone.utc)
    limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [limit]
    # Current usage for the period (e.g., $9.99 for the month)
    mock_backend.get_accounting_entries_for_quota.return_value = 9.99
    
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=0, cost=0.02 # Request cost is $0.02, total would be $10.01
    )
    
    assert is_allowed is False
    assert reason is not None
    
    # Define a side_effect function for mock_backend.get_usage_limits
    def get_usage_limits_side_effect_denied(scope: Optional[LimitScope] = None, model: Optional[str] = None, 
                                            username: Optional[str] = None, caller_name: Optional[str] = None, project_name: Optional[str] = None):
        if scope == LimitScope.USER and username == "test_user":
            return [limit] 
        return []

    mock_backend.get_usage_limits.side_effect = get_usage_limits_side_effect_denied # Use unique name
    # Reset mocks before the second call to check_quota
    mock_backend.get_accounting_entries_for_quota.reset_mock()
    mock_backend.get_usage_limits.reset_mock() # Also reset this one
    mock_backend.get_accounting_entries_for_quota.return_value = 9.99 # Ensure it's set for the re-run

    # Re-run check_quota
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=0, cost=0.02 
    )
    assert is_allowed is False # Should still be false
    assert reason is not None

    # Corrected expected message: QuotaService uses the 'limit_scope_for_message' passed to _evaluate_limits.
    # _check_user_limits passes "USER".
    assert "USER (user: test_user) limit: 10.00 cost per 1 month" in reason
    assert "current usage: 9.99, request: 0.02" in reason

    # Verify calls
    mock_backend.get_usage_limits.assert_any_call(scope=LimitScope.USER, username="test_user")
    mock_backend.get_accounting_entries_for_quota.assert_called_once()


def test_check_quota_multiple_limits_one_exceeded(quota_service: QuotaService, mock_backend: MagicMock):
    """Test check_quota with multiple limits, where one is exceeded."""
    now = datetime.now(timezone.utc)
    cost_limit = UsageLimitDTO(
        id=1, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
        max_value=10.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    request_limit = UsageLimitDTO(
        id=2, scope=LimitScope.USER.value, limit_type=LimitType.REQUESTS.value,
        max_value=100.0, interval_unit=TimeInterval.DAY.value, interval_value=1,
        username="test_user", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [cost_limit, request_limit]

    # Scenario: Cost is fine, but requests are exceeded
    def get_accounting_side_effect(start_time, limit_type, model, username, caller_name, project_name, filter_project_null):
        if limit_type == LimitType.COST:
            return 5.0 # Well within $10 cost limit
        elif limit_type == LimitType.REQUESTS:
            return 100.0 # Already at 100 requests, next one (count as 1) will exceed
        return 0.0
    
    mock_backend.get_accounting_entries_for_quota.side_effect = get_accounting_side_effect
    
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=10, cost=0.01 # Request cost is $0.01, request count is 1
    )
    
    assert is_allowed is False
    assert reason is not None

    # Define a side_effect for get_usage_limits
    def get_usage_limits_side_effect_multiple(scope: Optional[LimitScope] = None, model: Optional[str] = None, 
                                              username: Optional[str] = None, caller_name: Optional[str] = None, project_name: Optional[str] = None):
        if scope == LimitScope.USER and username == "test_user":
            return [cost_limit, request_limit] # Return both user-specific limits
        return []

    mock_backend.get_usage_limits.side_effect = get_usage_limits_side_effect_multiple # Corrected name
    
    # Reset get_accounting_entries_for_quota mock and set its new side_effect for this test
    mock_backend.get_accounting_entries_for_quota.reset_mock()
    mock_backend.get_accounting_entries_for_quota.side_effect = get_accounting_side_effect

    # Re-run check_quota
    is_allowed, reason = quota_service.check_quota(
        model="gpt-4", username="test_user", caller_name="test_caller",
        input_tokens=10, cost=0.01 
    )
    assert is_allowed is False # Should still be false
    assert reason is not None

    # The failure message will be for the first limit that's hit (REQUESTS in this case).
    # Expected scope message is "USER" as these are user limits.
    assert "USER (user: test_user) limit: 100.00 requests per 1 day" in reason
    assert "current usage: 100.00, request: 1.00" in reason # Corrected float formatting

    # Verify calls
    mock_backend.get_usage_limits.assert_any_call(scope=LimitScope.USER, username="test_user")
    # get_accounting_entries_for_quota will be called for COST limit (passes) and then for REQUESTS limit (fails)
    assert mock_backend.get_accounting_entries_for_quota.call_count == 2


def test_check_quota_different_scopes(quota_service: QuotaService, mock_backend: MagicMock):
    """Test that limits are fetched with combined scopes if applicable."""
    # QuotaService currently fetches limits by ORing scope attributes in get_usage_limits call.
    # The mock_backend.get_usage_limits is called once with all relevant user, model, caller.
    # So, this test mainly ensures the call to get_usage_limits is made as expected.
    
    mock_backend.get_usage_limits.return_value = [] # No limits for simplicity
    
    quota_service.check_quota(
        model="super_model", username="super_user", caller_name="super_caller",
        input_tokens=1, cost=0.001
    )
    
    # Based on the QuotaService logic, it will make multiple calls for different scopes.
    # The specific parameters for each call depend on how QuotaService constructs them.
    # MODEL: model="super_model"
    # GLOBAL: (no specific entity filters)
    # USER: username="super_user"
    # CALLER (general): caller_name="super_caller", username=None
    # CALLER (user+caller): username="super_user", caller_name="super_caller"

    # Corrected order: MODEL, USER, CALLER (general), CALLER (user+caller), GLOBAL
    # Parameters not specified in the call from QuotaService will default to None.
    
    # Define expected calls as a list of dictionaries for manual comparison
    expected_calls_data = [
        {"scope": LimitScope.MODEL, "model": "super_model", "username": None, "caller_name": None},
        {"scope": LimitScope.USER, "username": "super_user", "model": None, "caller_name": None},
        {"scope": LimitScope.CALLER, "caller_name": "super_caller", "username": None, "model": None}, # General caller limit
        {"scope": LimitScope.CALLER, "username": "super_user", "caller_name": "super_caller", "model": None},  # User + Caller specific limit
        {"scope": LimitScope.GLOBAL, "model": None, "username": None, "caller_name": None} # GLOBAL is checked last
    ]

    actual_calls = mock_backend.get_usage_limits.call_args_list
    assert len(actual_calls) == len(expected_calls_data), \
        f"Expected {len(expected_calls_data)} calls, but got {len(actual_calls)}. Actual calls: {actual_calls}"

    actual_calls_kwargs_list = [c.kwargs for c in actual_calls]

    for expected_kwargs_item in expected_calls_data:
        found_match = False
        # Try to find a match in a way that respects that actual_kwargs_item might have more keys (if defaults are added by mock)
        # but all keys in expected_kwargs_item must match.
        for actual_kwargs_item in actual_calls_kwargs_list:
            match = True
            if not (actual_kwargs_item.get('scope') == expected_kwargs_item['scope'] and
                    actual_kwargs_item.get('model') == expected_kwargs_item.get('model') and
                    actual_kwargs_item.get('username') == expected_kwargs_item.get('username') and
                    actual_kwargs_item.get('caller_name') == expected_kwargs_item.get('caller_name') and
                    actual_kwargs_item.get('project_name') == expected_kwargs_item.get('project_name')):
                match = False
            
            if match:
                found_match = True
                # To ensure each actual call is matched at most once (like assert_has_calls with any_order=True)
                # we can remove it from a temporary list. For simplicity here, if distinct expected calls, this is okay.
                # If expected calls could be identical, a more complex removal strategy is needed.
                # For this test, expected_calls_data are distinct.
                break 
        assert found_match, f"Expected call with kwargs {expected_kwargs_item} not found in actual calls. Actual calls: {actual_calls_kwargs_list}"
    
    # Also verify the total number of calls if it's strictly 5 (already covered by len assertion)
    assert mock_backend.get_usage_limits.call_count == 5


def test_check_quota_token_limits(quota_service: QuotaService, mock_backend: MagicMock):
    """Test check_quota for input token limits."""
    now = datetime.now(timezone.utc)
    token_limit = UsageLimitDTO(
        id=1, scope=LimitScope.MODEL.value, limit_type=LimitType.INPUT_TOKENS.value,
        max_value=1000.0, interval_unit=TimeInterval.HOUR.value, interval_value=1,
        model="text-davinci-003", created_at=now, updated_at=now
    )
    mock_backend.get_usage_limits.return_value = [token_limit]
    mock_backend.get_accounting_entries_for_quota.return_value = 950.0 # 950 tokens used this hour

    # Scenario 1: Allowed
    is_allowed, reason = quota_service.check_quota(
        model="text-davinci-003", username="any_user", caller_name="any_caller",
        input_tokens=50, cost=0.0 # 50 tokens requested
    )
    assert is_allowed is True
    assert reason is None

    # Scenario 2: Denied
    is_allowed, reason = quota_service.check_quota(
        model="text-davinci-003", username="any_user", caller_name="any_caller",
        input_tokens=51, cost=0.0 # 51 tokens requested, total 1001, limit 1000
    )
    assert is_allowed is False
    assert reason is not None

    # Define a side_effect for get_usage_limits
    def get_usage_limits_side_effect_model(scope: Optional[LimitScope] = None, model: Optional[str] = None, 
                                           username: Optional[str] = None, caller_name: Optional[str] = None, project_name: Optional[str] = None):
        if scope == LimitScope.MODEL and model == "text-davinci-003":
            return [token_limit] # Return the model-specific limit
        return []

    # Reset mocks and apply new side_effect for get_usage_limits
    # mock_backend.get_usage_limits.reset_mock() # Not strictly needed if calls are specific enough
    mock_backend.get_usage_limits.side_effect = get_usage_limits_side_effect_model
    mock_backend.get_accounting_entries_for_quota.reset_mock()
    mock_backend.get_accounting_entries_for_quota.return_value = 950.0 # Set for this scenario

    # Re-run the denied scenario check
    is_allowed, reason = quota_service.check_quota(
        model="text-davinci-003", username="any_user", caller_name="any_caller",
        input_tokens=51, cost=0.0 
    )
    assert is_allowed is False # Should still be false
    assert reason is not None

    # This is a MODEL limit, so the scope in message should be MODEL
    assert "MODEL (model: text-davinci-003) limit: 1000.00 input_tokens per 1 hour" in reason
    assert "current usage: 950.00, request: 51.00" in reason # Values are formatted to .2f

    # Verify calls
    mock_backend.get_usage_limits.assert_any_call(scope=LimitScope.MODEL, model="text-davinci-003")
    mock_backend.get_accounting_entries_for_quota.assert_called_once()


def test_get_period_start_monthly(quota_service: QuotaService):
    """Test _get_period_start for monthly interval."""
    # Test for a specific date
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service._get_period_start(current_time, TimeInterval.MONTH, 1)
    assert period_start == datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Test for beginning of month
    current_time = datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    period_start = quota_service._get_period_start(current_time, TimeInterval.MONTH, 1)
    assert period_start == datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_daily(quota_service: QuotaService):
    """Test _get_period_start for daily interval."""
    current_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    period_start = quota_service._get_period_start(current_time, TimeInterval.DAY, 1)
    assert period_start == datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)

def test_get_period_start_hourly(quota_service: QuotaService):
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
