from datetime import timedelta
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits
from llm_accounting.models.accounting import AccountingEntry


class TestMonthRollingLimits(BaseTestRollingLimits):
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
        self.assertIn("GLOBAL limit: 3.00 requests per 3 monthly_rolling exceeded.", message)
        self.assertIn("Current usage: 3.00, request: 1.00.", message)
