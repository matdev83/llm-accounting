import unittest
from unittest.mock import MagicMock

from llm_accounting import LLMAccounting


class TestLLMAccountingAPI(unittest.TestCase):
    def test_llm_accounting_api_methods_and_properties_exist(self) -> None:
        mock_backend = MagicMock()
        accounting = LLMAccounting(backend=mock_backend)
        self.assertIsNotNone(accounting)

        # Check for properties
        self.assertTrue(hasattr(accounting, "backend"))
        self.assertTrue(hasattr(accounting, "quota_service"))

        # Check for methods
        methods = [
            "__enter__",
            "__exit__",
            "track_usage",
            "insert_api_request",
            "get_period_stats",
            "get_model_stats",
            "get_model_rankings",
            "purge",
            "tail",
            "check_quota",
            "set_usage_limit",
            "get_usage_limits",
            "delete_usage_limit",
        ]
        for method_name in methods:
            self.assertTrue(hasattr(accounting, method_name), f"Method {method_name} not found")
            self.assertTrue(callable(getattr(accounting, method_name)), f"{method_name} is not callable")

if __name__ == "__main__":
    unittest.main()
