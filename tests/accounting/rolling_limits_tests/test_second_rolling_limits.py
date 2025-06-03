import sys
from datetime import timedelta
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits


class TestSecondRollingLimits(BaseTestRollingLimits):
    def test_basic_second_rolling_limit_within_limit(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=5,
            interval_unit=TimeInterval.SECOND_ROLLING.value,
            interval_value=10, # 10 seconds rolling window
        )
        self._add_usage_limit(limit_dto)

        # Add usage within the last 10 seconds
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=1))
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=3))
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=5))

        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10,
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        self.assertTrue(allowed, f"Quota should be allowed. Message: {message}")
        self.assertIsNone(message)

    def test_basic_second_rolling_limit_exceed_limit(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=3,
            interval_unit=TimeInterval.SECOND_ROLLING.value,
            interval_value=10, # 10 seconds rolling window
        )
        self._add_usage_limit(limit_dto)

        # Add usage within the last 10 seconds
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=1))
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=3))
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=5)) # This is the 3rd request

        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10, # This would be the 4th request
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        print(f"TEST DEBUG: allowed={allowed}, message={message}", file=sys.stderr)
        self.assertFalse(allowed, "Quota should be denied.")
        self.assertIsNotNone(message)
        self.assertIn("GLOBAL limit: 3.00 requests per 10 second_rolling exceeded.", message)
        self.assertIn("Current usage: 3.00, request: 1.00.", message)

    def test_second_rolling_limit_usage_outside_window(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=2,
            interval_unit=TimeInterval.SECOND_ROLLING.value,
            interval_value=5, # 5 seconds rolling window
        )
        self._add_usage_limit(limit_dto)

        # This usage is outside the 5-second window from `self.now`
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=10))
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=7))

        # This usage is within the window
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=1))

        # Current request + the one recent entry = 2. Should be allowed.
        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10,
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        self.assertTrue(allowed, f"Quota should be allowed. Message: {message}")
        self.assertIsNone(message)

        # Simulate that the first request was actually made by adding an entry for it
        # This entry should be recent enough to be counted by the next check_quota call.
        # The parameters for this entry should match those that would be relevant for the limit.
        # For a GLOBAL request limit, any distinct request counts.
        # We use self.now for the timestamp to ensure it's within the window of the next check.
        self._add_accounting_entry(
            timestamp=self.now, # Simulate this request happening right now
            model="test-model", # Match the model being checked
            username="test-user", # Match the user
            caller_name="test-caller", # Match the caller
            project_name="test-project", # Match the project
            cost=0.01, # Match the cost
            input_tokens=10, # Match input tokens
            output_tokens=20, # Match output tokens
            execution_time=0.1 # Provide execution time
        )
        # Now there are 2 entries in the window:
        # 1. self.now - timedelta(seconds=1)
        # 2. self.now (just added)

        # Adding one more request (represented by the check_quota call) should exceed the limit (2+1 > 2)
        allowed, message = self.quota_service.check_quota(
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10,
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        self.assertFalse(allowed, "Quota should be denied on the second check.")
        self.assertIsNotNone(message)
        self.assertIn("GLOBAL limit: 2.00 requests per 5 second_rolling", message)
        # After the first check_quota, one request was virtually added, making current usage 1 (from self.now - timedelta(seconds=1)) + 1 (from first check_quota).
        # This is a bit tricky because check_quota itself doesn't persist the request it's checking.
        # The test setup implies that the _evaluate_limits will count the current request.
        # The current usage from DB is 1 (from self.now - timedelta(seconds=1)). The request is 1. Total 2.
        # For the *next* call, if the previous one was hypothetically added, usage would be 2.
        # Let's re-evaluate how current_usage is reported in the message.
        # The message reports DB usage + current request.
        # So, for the second call: DB usage is 1. Current request is 1. This sums to 2. Limit is 2. This should be allowed.
        # The test is designed as if the check_quota *persists* the request, which it doesn't.
        # Let's adjust the expectation or the test logic.

        # Re-testing the "exceeding" part more directly:
        # Add one more entry to definitely exceed.
        # DB has:
        #  1. self.now - timedelta(seconds=1) (Original one, let's call it Entry A)
        #  2. self.now (Simulated first request, let's call it Entry B)
        # Now add Entry C:
        self._add_accounting_entry(timestamp=self.now - timedelta(seconds=2)) # Entry C
        # All three (A, B, C) should be within a 5-second window of the next check_quota call.
        # So, current usage from DB should be 3.

        allowed, message = self.quota_service.check_quota( # This is the 4th request (3 existing + this one)
            model="test-model",
            username="test-user",
            caller_name="test-caller",
            input_tokens=10,
            cost=0.01,
            project_name="test-project",
            completion_tokens=20,
        )
        self.assertFalse(allowed, "Quota should be denied after adding another entry.")
        self.assertIsNotNone(message)
        self.assertIn("GLOBAL limit: 2.00 requests per 5 second_rolling exceeded.", message) # Ensure plural for value > 1
        self.assertIn("Current usage: 3.00, request: 1.00.", message) # Corrected expected usage
