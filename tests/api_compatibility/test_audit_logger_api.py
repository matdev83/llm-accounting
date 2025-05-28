import unittest
from unittest.mock import MagicMock, Mock

from llm_accounting.audit_log import AuditLogger
from llm_accounting.backends.base import BaseBackend, AuditLogEntry


class TestAuditLoggerAPI(unittest.TestCase):
    def setUp(self):
        self.mock_backend = Mock(spec=BaseBackend)
        self.logger = AuditLogger(backend=self.mock_backend)

    def test_audit_logger_api_methods_exist(self) -> None:
        # Check for methods
        methods = [
            "log_event",
            "log_prompt",
            "log_response",
            "get_entries",
        ]
        for method_name in methods:
            self.assertTrue(hasattr(self.logger, method_name), f"Method {method_name} not found")
            self.assertTrue(callable(getattr(self.logger, method_name)), f"{method_name} is not callable")

    def test_log_event_delegates_to_backend(self):
        self.logger.log_event(
            app_name="test_app",
            user_name="test_user",
            model="test_model",
            log_type="test_type",
            prompt_text="test_prompt",
            response_text="test_response",
            remote_completion_id="test_id",
            project="test_project"
        )
        self.mock_backend.log_audit_event.assert_called_once()
        args, kwargs = self.mock_backend.log_audit_event.call_args
        entry = args[0]
        self.assertIsInstance(entry, AuditLogEntry)
        self.assertEqual(entry.app_name, "test_app")
        # Add more assertions for other fields if necessary

    def test_log_prompt_delegates_to_backend(self):
        self.logger.log_prompt(
            app_name="test_app",
            user_name="test_user",
            model="test_model",
            prompt_text="test_prompt"
        )
        self.mock_backend.log_audit_event.assert_called_once()
        args, kwargs = self.mock_backend.log_audit_event.call_args
        entry = args[0]
        self.assertIsInstance(entry, AuditLogEntry)
        self.assertEqual(entry.log_type, "prompt")
        self.assertEqual(entry.prompt_text, "test_prompt")

    def test_log_response_delegates_to_backend(self):
        self.logger.log_response(
            app_name="test_app",
            user_name="test_user",
            model="test_model",
            response_text="test_response"
        )
        self.mock_backend.log_audit_event.assert_called_once()
        args, kwargs = self.mock_backend.log_audit_event.call_args
        entry = args[0]
        self.assertIsInstance(entry, AuditLogEntry)
        self.assertEqual(entry.log_type, "response")
        self.assertEqual(entry.response_text, "test_response")

    def test_get_entries_delegates_to_backend(self):
        self.logger.get_entries(app_name="filter_app")
        self.mock_backend.get_audit_log_entries.assert_called_once_with(
            app_name="filter_app",
            start_date=None, end_date=None, user_name=None, project=None, log_type=None, limit=None
        )


if __name__ == "__main__":
    unittest.main()
