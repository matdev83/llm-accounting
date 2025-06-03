from datetime import timedelta
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits


class TestWeekRollingLimits(BaseTestRollingLimits):
    def test_week_rolling_limit_cost(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.CALLER.value,
            caller_name="test-caller",
            limit_type=LimitType.COST.value,
            max_value=25.00,
            interval_unit=TimeInterval.WEEK_ROLLING.value,
            interval_value=2, # 2 weeks rolling window
        )
        self._add_usage_limit(limit_dto)

        # Usage within the last 2 weeks
        self._add_accounting_entry(timestamp=self.now - timedelta(days=3), caller_name="test-caller", cost=10.0)
        self._add_accounting_entry(timestamp=self.now - timedelta(days=10), caller_name="test-caller", cost=7.50)
        # Usage outside window
        self._add_accounting_entry(timestamp=self.now - timedelta(days=20), caller_name="test-caller", cost=5.0)
        # Usage for another caller
        self._add_accounting_entry(timestamp=self.now - timedelta(days=1), caller_name="other-caller", cost=2.0)

        # Current cost for "test-caller": 10.0 + 7.50 = 17.50
        # Requesting cost of 5.0. Total = 22.50. Should be allowed.
        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            project_name="test-project", input_tokens=0, completion_tokens=0, cost=5.0
        )
        self.assertTrue(allowed, f"Quota should be allowed. Message: {message}")
        self.assertIsNone(message)

        # Requesting cost of 8.0. Total = 17.50 + 8.0 = 25.50. Should exceed.
        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            project_name="test-project", input_tokens=0, completion_tokens=0, cost=8.0
        )
        self.assertFalse(allowed, "Quota should be denied.")
        self.assertIsNotNone(message)
        self.assertIn("CALLER (caller: test-caller) limit: 25.00 cost per 2 week_rolling exceeded.", message)
        self.assertIn("Current usage: 17.50, request: 8.00.", message)
