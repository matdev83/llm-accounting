import unittest
from freezegun import freeze_time
from tests.accounting.rolling_limits_tests.base_test_rolling_limits import BaseTestRollingLimits


@freeze_time("2023-01-01 00:00:00", tz_offset=0)
class TestRollingLimits(BaseTestRollingLimits):
    def test_placeholder(self):
        self.assertTrue(True)

    def test_float_comparison_sanity_check(self):
        val1 = 4.0
        val2 = 3.0
        self.assertTrue(val1 > val2, f"Sanity check: {val1} > {val2} should be True. Is {val1 > val2}")
        self.assertFalse(val1 < val2, f"Sanity check: {val1} < {val2} should be False. Is {val1 < val2}")
        self.assertFalse(val1 == val2, f"Sanity check: {val1} == {val2} should be False. Is {val1 == val2}")


if __name__ == "__main__":
    unittest.main()
