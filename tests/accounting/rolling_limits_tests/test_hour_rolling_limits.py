from datetime import timedelta
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits


class TestHourRollingLimits(BaseTestRollingLimits):
    def test_no_usage_rolling_limit(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=5,
            interval_unit=TimeInterval.HOUR_ROLLING.value,
            interval_value=1, # 1 hour rolling window
        )
        self._add_usage_limit(limit_dto)

        # No prior usage
        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10,
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        self.assertTrue(allowed, f"Quota should be allowed with no prior usage. Message: {message}")
        self.assertIsNone(message)

    def test_hour_rolling_boundary_just_inside(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=1,
            interval_unit=TimeInterval.HOUR_ROLLING.value,
            interval_value=1, # 1 hour rolling window
        )
        self._add_usage_limit(limit_dto)

        # Usage exactly 1 hour - 1 second ago (just inside the window)
        self._add_accounting_entry(timestamp=self.now - timedelta(hours=1) + timedelta(seconds=1))

        # This request should exceed the limit
        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10,
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        self.assertFalse(allowed, "Quota should be denied.")
        self.assertIsNotNone(message)
        self.assertIn("GLOBAL limit: 1.00 requests per 1 hour_rolling exceeded.", message)
        self.assertIn("Current usage: 1.00, request: 1.00.", message)


    def test_hour_rolling_boundary_just_outside(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=1,
            interval_unit=TimeInterval.HOUR_ROLLING.value,
            interval_value=1, # 1 hour rolling window
        )
        self._add_usage_limit(limit_dto)

        # Usage exactly 1 hour ago (just outside the window, rolling period is current_time - duration)
        self._add_accounting_entry(timestamp=self.now - timedelta(hours=1))

        # This request should be allowed as the previous one is now outside
        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10,
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        self.assertFalse(allowed, "Quota should be denied.")
        self.assertIsNotNone(message)
        self.assertIn("GLOBAL limit: 1.00 requests per 1 hour_rolling exceeded.", message)
        self.assertIn("Current usage: 1.00, request: 1.00.", message)
