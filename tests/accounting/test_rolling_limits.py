import unittest
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.base import Base
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from llm_accounting.models.accounting import AccountingEntry
from llm_accounting.services.quota_service import QuotaService


class TestRollingLimits(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        # Use an in-memory SQLite database for testing
        # self.engine = create_engine("sqlite:///:memory:") # Engine created by SQLiteBackend
        # Base.metadata.create_all(self.engine) # Schema handled by SQLiteBackend.initialize()
        # Session = sessionmaker(bind=self.engine)
        # self.session = Session()

        self.backend = SQLiteBackend(db_path=":memory:")
        self.backend.initialize() # This should create tables and self.backend.engine

        # Create a session for test helper methods to use, bound to the backend's engine
        TestSession = sessionmaker(bind=self.backend.engine)
        self.session = TestSession()

        self.quota_service = QuotaService(backend=self.backend)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        # Base.metadata.drop_all(self.engine) # Tables are in-memory, will be gone
        # self.session.close() # Session managed by backend or not used directly by tests
        if self.backend:
            self.backend.close() # Close the connection held by the backend

    def _add_usage_limit(self, limit_dto: UsageLimitDTO):
        self.backend.insert_usage_limit(limit_dto)

    def _add_accounting_entry(
        self,
        timestamp: datetime,
        model: str = "test-model",
        username: str = "test-user",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        project_name: Optional[str] = None,
        caller_name: Optional[str] = None,
        execution_time: float = 0.1, # Added default execution_time
    ):
        entry = AccountingEntry(
            timestamp=timestamp, # Corrected from request_time
            model=model, # Corrected from model_name
            username=username,
            prompt_tokens=input_tokens, # Corrected from input_tokens
            completion_tokens=output_tokens, # Corrected from output_tokens
            cost=cost,
            project=project_name, # Corrected from project_name
            caller_name=caller_name,
            execution_time=execution_time, # Added
        )
        self.session.add(entry)
        self.session.commit()

    def test_placeholder(self):
        self.assertTrue(True)

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
        # Configure logging for this specific test run to capture DEBUG messages
        import logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
        self.assertFalse(allowed, "Quota should be denied.")
        self.assertIsNotNone(message)
        self.assertIn("GLOBAL limit: 3.00 requests per 10 second_rolling", message)
        self.assertIn("current usage: 3.00, request: 1.00", message)

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
        self.assertIn("GLOBAL limit: 2.00 requests per 5 second_rollings", message) # Ensure plural for value > 1
        self.assertIn("current usage: 3.00, request: 1.00", message) # Corrected expected usage

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
        self.assertIn("USER (user: test-user) limit: 1000.00 input_tokens per 5 minute_rolling", message)
        self.assertIn("current usage: 700.00, request: 350.00", message)

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
        self.assertIn("current usage: 1.00, request: 1.00", message)


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
        self.assertTrue(allowed, f"Quota should be allowed. Message: {message}")
        self.assertIsNone(message)

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

        # Current usage for "test-project": 2000 + 1500 = 3500
        # Requesting 1000 output_tokens. Total = 4500. Should be allowed.
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
        self.assertIn("PROJECT (project: test-project) limit: 5000.00 output_tokens per 1 day_rolling", message)
        self.assertIn("current usage: 3500.00, request: 2000.00", message)

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
        self.assertIn("CALLER (caller: test-caller) limit: 25.00 cost per 2 week_rolling", message)
        self.assertIn("current usage: 17.50, request: 8.00", message)

    def test_month_rolling_limit_requests(self):
        limit_dto = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=100,
            interval_unit=TimeInterval.MONTH_ROLLING.value,
            interval_value=3, # 3 months rolling window
        )
        self._add_usage_limit(limit_dto)

        # Usage within the last 3 months
        self._add_accounting_entry(timestamp=self.now - timedelta(days=15)) # current month
        self._add_accounting_entry(timestamp=self.now - timedelta(days=45)) # previous month
        self._add_accounting_entry(timestamp=self.now - timedelta(days=75)) # month before previous

        # Simulate a bit more complex history for month rolling
        # Current month: 1 entry
        # M-1: 1 entry
        # M-2: 1 entry
        # M-3: (now - timedelta(days=105)) - this should be outside a 3-month rolling window from self.now
        # Let's adjust self.now slightly to make calculations more predictable for month boundaries
        # For simplicity, assume self.now is mid-month, e.g., April 15th.
        # A 3-month rolling window would mean (April 15, March, February). Jan 15 would be out.
        # self.now - timedelta(days=75) is roughly 2.5 months ago.
        # self.now - timedelta(days=105) is roughly 3.5 months ago.

        # Add one more entry that should be outside the 3-month window
        # To be precise with _get_period_start for MONTH_ROLLING:
        # start_time is current_time.replace(year=final_year, month=final_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        # where final_month is derived from (current_time.year * 12 + (current_time.month - 1) - interval_value)

        # For a 3 month interval_value, if current is April, period_start is Feb 1st.
        # So, entries from Feb 1st, March 1st, April (up to now) count. Jan entries don't.

        # Let current be April 15th.
        # M-0 (April): self.now - timedelta(days=5) -> Counts
        # M-1 (March): self.now - timedelta(days=35) -> Counts
        # M-2 (Feb): self.now - timedelta(days=65) -> Counts
        # M-3 (Jan): self.now - timedelta(days=95) -> Should NOT count for a 3-month rolling period starting Feb 1st

        self.session.query(AccountingEntry).delete() # Clear previous entries for this test
        self.session.commit()

        self._add_accounting_entry(timestamp=self.now - timedelta(days=5))  # Counts (current month)
        self._add_accounting_entry(timestamp=self.now - timedelta(days=35)) # Counts (previous month)
        self._add_accounting_entry(timestamp=self.now - timedelta(days=65)) # Counts (month before previous)
        self._add_accounting_entry(timestamp=self.now - timedelta(days=95)) # Should NOT count

        # Current usage = 3 requests. Max is 100.
        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            input_tokens=1, cost=0.01, project_name="test-project"
        )
        self.assertTrue(allowed, f"Quota should be allowed. Usage: 3. Message: {message}")
        self.assertIsNone(message)

        # Check current usage reported by backend for this specific limit
        # This requires a way to get current usage directly, which is not the primary goal of check_quota
        # However, the message from a failed check_quota gives us this. Let's force a failure.

        limit_dto_strict = UsageLimitDTO(
            scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value, max_value=3,
            interval_unit=TimeInterval.MONTH_ROLLING.value, interval_value=3,
        )
        # Remove the old limit and add a new one, or update it if backend supports it.
        # For simplicity, let's assume we can clear and add.
        # self.session.query(UsageLimitDTO).delete() # This is not how DTOs are stored. Limits are in DB.

        # To clear previous limits for this test, we can use the backend's purge or delete methods
        # For now, let's assume tests are independent or manage state via specific deletions if needed.
        # A better way would be to use backend.delete_usage_limit if an ID is known, or a targeted delete.
        # For this specific test, clearing all limits of a certain type might be needed.
        # The existing tests use a fresh DB per test via fixtures, which is cleaner.
        # Here, we might need to manually clear:
        # Get all global request limits and delete them by ID before adding the new one.

        # Let's find and delete existing global request month_rolling limits to avoid conflicts
        # Fetch all global limits first
        existing_global_limits = self.backend.get_usage_limits(scope=LimitScope.GLOBAL)

        for limit in existing_global_limits:
            # Filter in Python code
            if (limit.limit_type == LimitType.REQUESTS.value and
                limit.interval_unit == TimeInterval.MONTH_ROLLING.value):
                 if limit.id: self.backend.delete_usage_limit(limit.id)

        self._add_usage_limit(limit_dto_strict)

        # Clear previous accounting entries before adding new ones for this specific check
        self.session.query(AccountingEntry).delete()
        self.session.commit()

        # Re-add the entries for the strict limit test
        self._add_accounting_entry(timestamp=self.now - timedelta(days=5))
        self._add_accounting_entry(timestamp=self.now - timedelta(days=35))
        self._add_accounting_entry(timestamp=self.now - timedelta(days=65))
        self._add_accounting_entry(timestamp=self.now - timedelta(days=95)) # Still should not count

        # This request (1) + existing (3) = 4. Limit is 3. Should fail.
        allowed, message = self.quota_service.check_quota(
            model="test-model", username="test-user", caller_name="test-caller",
            input_tokens=1, cost=0.01, project_name="test-project"
        )
        self.assertFalse(allowed, "Quota should be denied with strict limit.")
        self.assertIsNotNone(message)
        # For interval_value > 1, 'monthly_rolling' becomes 'monthly_rollings'
        self.assertIn("GLOBAL limit: 3.00 requests per 3 monthly_rollings", message)
        self.assertIn("current usage: 3.00, request: 1.00", message)

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
        self.assertIn("GLOBAL limit: 5.00 requests per 10 second_rolling", message)
        # current usage in message will be 6 (from DB) + 1 (request) = 7. Limit is 5.
        self.assertIn("current usage: 6.00, request: 1.00", message)

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
        self.assertIn("GLOBAL limit: 2.00 requests per 1 minute_rolling", message)
        self.assertIn("current usage: 2.00, request: 1.00", message)


if __name__ == "__main__":
    unittest.main()
