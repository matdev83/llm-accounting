import unittest
from unittest.mock import MagicMock, call
from datetime import datetime

# Updated imports: Added UsageLimitData and relevant enums
from llm_accounting import LLMAccounting, UsageLimitDTO, LimitScope, LimitType, TimeInterval
from llm_accounting.backends.base import UsageEntry, UsageStats # For type hints if needed elsewhere


class TestLLMAccountingAPI(unittest.TestCase):
    def setUp(self):
        """Set up for each test."""
        self.mock_backend = MagicMock()
        # Configure the backend mock to return something for get_db_path if needed by LLMAccounting init or methods
        self.mock_backend.db_path = None # Assuming it's not a SQLite backend for these general tests
        self.accounting = LLMAccounting(backend=self.mock_backend)

    def test_llm_accounting_api_methods_and_properties_exist(self) -> None:
        self.assertIsNotNone(self.accounting)

        # Check for properties
        self.assertTrue(hasattr(self.accounting, "backend"))
        self.assertTrue(hasattr(self.accounting, "quota_service"))

        # Check for methods
        methods = [
            "__enter__",
            "__exit__",
            "track_usage",
            "get_period_stats",
            "get_model_stats",
            "get_model_rankings",
            "purge",
            "tail",
            "check_quota",
            "set_usage_limit",
            "get_usage_limits",
            "delete_usage_limit",
            "get_db_path", # Added get_db_path as it's in the class
        ]
        for method_name in methods:
            self.assertTrue(hasattr(self.accounting, method_name), f"Method {method_name} not found")
            self.assertTrue(callable(getattr(self.accounting, method_name)), f"{method_name} is not callable")

    def test_set_usage_limit_passes_usage_limit_data_to_backend(self) -> None:
        """Test that set_usage_limit calls backend.insert_usage_limit with UsageLimitData."""
        scope = LimitScope.USER
        limit_type = LimitType.COST
        interval_unit = TimeInterval.MONTH
        max_value = 100.0
        interval_value = 1
        username = "test_user"

        self.accounting.set_usage_limit(
            scope=scope,
            limit_type=limit_type,
            max_value=max_value,
            interval_unit=interval_unit,
            interval_value=interval_value,
            username=username
        )

        self.mock_backend.insert_usage_limit.assert_called_once()
        args, _ = self.mock_backend.insert_usage_limit.call_args
        limit_arg = args[0]

        self.assertIsInstance(limit_arg, UsageLimitDTO)
        self.assertEqual(limit_arg.scope, scope.value) # Enums should be passed as their string values
        self.assertEqual(limit_arg.limit_type, limit_type.value)
        self.assertEqual(limit_arg.max_value, max_value)
        self.assertEqual(limit_arg.interval_unit, interval_unit.value)
        self.assertEqual(limit_arg.interval_value, interval_value)
        self.assertEqual(limit_arg.username, username)
        self.assertIsNone(limit_arg.model) # Not specified, should be None
        self.assertIsNone(limit_arg.caller_name) # Not specified, should be None
        # id, created_at, updated_at are typically set by the backend or DB, so not checked here for exact values
        # unless LLMAccounting explicitly sets them before passing to backend.
        # The current LLMAccounting.set_usage_limit creates UsageLimitData without id, created_at, updated_at.

    def test_get_usage_limits_returns_list_of_usage_limit_data_from_backend(self) -> None:
        """Test that get_usage_limits returns a list of UsageLimitData from the backend."""
        mock_limit_data = UsageLimitDTO(
            id=1,
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=1000.0,
            interval_unit=TimeInterval.DAY.value,
            interval_value=1,
            model=None,
            username=None,
            caller_name=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.mock_backend.get_usage_limits.return_value = [mock_limit_data]

        # Call get_usage_limits with some example filters
        scope_filter = LimitScope.GLOBAL
        model_filter = "gpt-4"
        
        result_limits = self.accounting.get_usage_limits(scope=scope_filter, model=model_filter)

        # Assert that the backend method was called with the correct filter values
        self.mock_backend.get_usage_limits.assert_called_once_with(
            scope=scope_filter, model=model_filter, username=None, caller_name=None, project_name=None
        )

        self.assertIsInstance(result_limits, list)
        self.assertEqual(len(result_limits), 1)
        
        retrieved_limit = result_limits[0]
        self.assertIsInstance(retrieved_limit, UsageLimitDTO)
        self.assertEqual(retrieved_limit.id, mock_limit_data.id)
        self.assertEqual(retrieved_limit.scope, mock_limit_data.scope)
        self.assertEqual(retrieved_limit.limit_type, mock_limit_data.limit_type)

    def test_delete_usage_limit_calls_backend(self) -> None:
        """Test that delete_usage_limit calls the backend method."""
        limit_id_to_delete = 123
        self.accounting.delete_usage_limit(limit_id_to_delete)
        self.mock_backend.delete_usage_limit.assert_called_once_with(limit_id_to_delete)


if __name__ == "__main__":
    unittest.main()
