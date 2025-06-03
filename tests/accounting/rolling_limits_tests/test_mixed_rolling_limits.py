from datetime import timedelta
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits


class TestMixedRollingLimits(BaseTestRollingLimits):
    def test_multiple_rolling_limits_one_exceeded(self):
        # Global: 5 requests / 10 sec rolling
        limit_global_req = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value, max_value=5,
            interval_unit=TimeInterval.SECOND_ROLLING.value, interval_value=10
        )
        self._add_usage_limit(limit_global_req)

        # User: 100 input tokens / 1 min rolling
        limit_user_tokens = UsageLimitDTO(
            scope=LimitScope.USER.value, username="test-user", limit_type=LimitType.INPUT_TOKENS.value, max_value=100,
            interval_unit=TimeInterval.MINUTE_ROLLING.value, interval_value=1
        )
        self._add_usage_limit(limit_user_tokens)

        # Add 6 requests for "test-user" in the last 5 seconds (violates global requests limit)
        for i in range(6):
            self._add_accounting_entry(timestamp=self.now - timedelta(seconds=i+1), username="test-user", input_tokens=10)

        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            input_tokens=10, cost=0.01, project_name="test-project" # This is the 7th request effectively for global
        )
        self.assertFalse(allowed, "Quota should be denied due to global request limit.")
        self.assertIsNotNone(message)
        self.assertIn("GLOBAL limit: 5.00 requests per 10 second_rolling exceeded.", message)
        # current usage in message will be 6 (from DB) + 1 (request) = 7. Limit is 5.
        self.assertIn("Current usage: 6.00, request: 1.00.", message)

    def test_mixed_fixed_and_rolling_limits_rolling_exceeded(self):
        # Fixed: 10 requests / day (fixed window)
        limit_fixed_day = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value, max_value=10,
            interval_unit=TimeInterval.DAY.value, interval_value=1
        )
        self._add_usage_limit(limit_fixed_day)

        # Rolling: 3 requests / 1 minute rolling
        limit_rolling_minute = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value, max_value=2, # Stricter to test easily
            interval_unit=TimeInterval.MINUTE_ROLLING.value, interval_value=1
        )
        self._add_usage_limit(limit_rolling_minute)

        # Add 2 requests in the last 30 seconds
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=10))
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=20))
        # Add 1 request 2 hours ago (counts for fixed daily, not for 1-min rolling)
        self._add_accounting_entry(timestamp=self.now - timedelta(hours=2))

        # Current state:
        # Fixed daily: 3 requests (10, 20 secs ago, 2 hrs ago) + 1 current = 4. Limit 10. OK.
        # Rolling minute: 2 requests (10, 20 secs ago) + 1 current = 3. Limit 2. FAIL.

        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            input_tokens=10, cost=0.01, project_name="test-project"
        )
        self.assertFalse(allowed, "Quota should be denied due to rolling minute limit.")
        self.assertIsNotNone(message)
        # The message indicates the 1 minute_rolling limit was hit
        self.assertIn("GLOBAL limit: 2.00 requests per 1 minute_rolling exceeded.", message)
        self.assertIn("Current usage: 2.00, request: 1.00.", message)
