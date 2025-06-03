from datetime import timedelta
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits


class TestMinuteRollingLimits(BaseTestRollingLimits):
    def test_minute_rolling_limit_input_tokens(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.USER.value, # User-specific limit
            username="test-user",
            limit_type=LimitType.INPUT_TOKENS.value,
            max_value=1000,
            interval_unit=TimeInterval.MINUTE_ROLLING.value,
            interval_value=5, # 5 minutes rolling window
        )
        self._add_usage_limit(limit_dto)

        # Usage within the window
        self._add_accounting_entry(
            timestamp=self.now - timedelta(minutes=1),
            username="test-user",
            input_tokens=300
        )
        self._add_accounting_entry(
            timestamp=self.now - timedelta(minutes=3),
            username="test-user",
            input_tokens=400
        )
        # Usage outside the window for the same user
        self._add_accounting_entry(
            timestamp=self.now - timedelta(minutes=10),
            username="test-user",
            input_tokens=500
        )
        # Usage for a different user (should not count)
        self._add_accounting_entry(
            timestamp=self.now - timedelta(minutes=2),
            username="other-user",
            input_tokens=200
        )

        # Current usage for "test-user" is 300 + 400 = 700 tokens.
        # Requesting 250 tokens. Total = 950. Should be allowed.
        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=250, # Requesting 250 tokens
            cost=0.01,
            project_name="test-project",
            completion_tokens=0,
        )
        self.assertTrue(allowed, f"Quota should be allowed. Message: {message}")
        self.assertIsNone(message)

        # Requesting 350 tokens. Total = 700 (existing) + 350 (request) = 1050. Should exceed.
        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=350, # Requesting 350 tokens
            cost=0.01,
            project_name="test-project",
            completion_tokens=0,
        )
        self.assertFalse(allowed, "Quota should be denied.")
        self.assertIsNotNone(message)
        self.assertIn("USER (user: test-user) limit: 1000.00 input_tokens per 5 minute_rolling exceeded.", message)
        self.assertIn("Current usage: 700.00, request: 350.00.", message)
