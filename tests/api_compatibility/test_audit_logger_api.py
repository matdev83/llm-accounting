import unittest
from unittest.mock import MagicMock

from llm_accounting import AuditLogger # Assuming AuditLogger is exported from llm_accounting

class TestAuditLoggerAPI(unittest.TestCase):
    def test_audit_logger_api_methods_and_properties_exist(self) -> None:
        # Use an in-memory SQLite database for testing to avoid creating files
        logger = AuditLogger(db_path=":memory:")
        self.assertIsNotNone(logger)

        # Check for properties
        self.assertTrue(hasattr(logger, "db_path"))
        self.assertTrue(hasattr(logger, "conn"))

        # Check for methods
        methods = [
            "connect",
            "close",
            "__enter__",
            "__exit__",
            "log_event",
            "log_prompt",
            "log_response",
        ]
        for method_name in methods:
            self.assertTrue(hasattr(logger, method_name), f"Method {method_name} not found")
            self.assertTrue(callable(getattr(logger, method_name)), f"{method_name} is not callable")

if __name__ == "__main__":
    unittest.main()
