from datetime import timedelta
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits


class TestDayRollingLimits(BaseTestRollingLimits):
    def test_day_rolling_limit_output_tokens(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.PROJECT.value,
            project_name="test-project",
            limit_type=LimitType.OUTPUT_TOKENS.value,
            max_value=5000,
            interval_unit=TimeInterval.DAY_ROLLING.value,
            interval_value=1, # 1 day rolling window
        )
        self._add_usage_limit(limit_dto)

        # Usage within the last day
        self._add_accounting_entry(
            timestamp=self.now - timedelta(hours=5),
            project_name="test-project",
            output_tokens=2000
        )
        self._add_accounting_entry(
            timestamp=self.now - timedelta(hours=10),
            project_name="test-project",
            output_tokens=1500
        )
        # Usage outside window
        self._add_accounting_entry(
            timestamp=self.now - timedelta(hours=25),
            project_name="test-project",
            output_tokens=1000
        )
        # Usage for another project
        self._add_accounting_entry(
            timestamp=self.now - timedelta(hours=2),
            project_name="other-project",
            output_tokens=500
        )
        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            project_name="test-project", input_tokens=0, completion_tokens=1000, cost=0
        )
        self.assertTrue(allowed, f"Quota should be allowed. Message: {message}")
        self.assertIsNone(message)

        # Requesting 2000 output_tokens. Total = 3500 + 2000 = 5500. Should exceed.
        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            project_name="test-project", input_tokens=0, completion_tokens=2000, cost=0
        )
        self.assertFalse(allowed, "Quota should be denied.")
        self.assertIsNotNone(message)
        self.assertIn("PROJECT (project: test-project) limit: 5000.00 output_tokens per 1 day_rolling exceeded.", message)
        self.assertIn("Current usage: 3500.00, request: 2000.00.", message)
