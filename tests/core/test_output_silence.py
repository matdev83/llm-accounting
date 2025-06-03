import unittest
import logging
from io import StringIO
from unittest.mock import patch, MagicMock # Added MagicMock
from datetime import datetime

from llm_accounting import LLMAccounting, AuditLogger, QuotaService
from tests.utils.concrete_mock_backend import ConcreteTestBackend
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval # For QuotaService test

# Library logger, which we want to ensure is silent by default
library_logger = logging.getLogger('llm_accounting')

class TestOutputSilence(unittest.TestCase):

    def setUp(self):
        # Store original properties of the library logger
        self.original_handlers = library_logger.handlers[:]
        self.original_level = library_logger.level
        self.original_propagate = library_logger.propagate

        # For these tests, we want to ensure that *even if* a user configured
        # the library logger to be very verbose (e.g., DEBUG) and added a
        # StreamHandler, our NullHandler (added in __init__.py) prevents output
        # unless the user *also* removes the NullHandler or sets propagate = True.
        # However, the primary goal is to test that *by default* (NullHandler present),
        # no output is seen.
        # We can also specifically test scenarios where print() might have been used.

        # It's also good practice for tests not to alter global state if possible,
        # but here we are testing the default behavior which relies on the NullHandler.
        # We will restore the logger state in tearDown.

        # To be absolutely sure for testing `print()` calls vs logging:
        # We can set the library logger to a high level.
        library_logger.setLevel(logging.CRITICAL + 1) # Effectively silence it for logging calls
        # Ensure it doesn't propagate to parent loggers that might print
        library_logger.propagate = False
        # Remove all handlers except the NullHandler (if it's there from __init__.py)
        # or add one if it's not (though the __init__.py should have added it)
        is_null_handler_present = any(isinstance(h, logging.NullHandler) for h in library_logger.handlers)
        if not is_null_handler_present:
            # This case should ideally not be hit if __init__.py is correctly modified
            library_logger.addHandler(logging.NullHandler())


    def tearDown(self):
        # Restore original logging configuration for the library logger
        library_logger.handlers = self.original_handlers
        library_logger.setLevel(self.original_level)
        library_logger.propagate = self.original_propagate

    @patch('sys.stdout', new_callable=StringIO)
    @patch('sys.stderr', new_callable=StringIO)
    def test_audit_logger_silence(self, mock_stderr, mock_stdout):
        mock_backend = ConcreteTestBackend()
        audit_logger = AuditLogger(backend=mock_backend)
        audit_logger.log_event(
            app_name="test_app",
            user_name="test_user",
            model="test_model",
            log_type="test_event"
        )
        self.assertEqual(mock_stdout.getvalue(), "")
        self.assertEqual(mock_stderr.getvalue(), "")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('sys.stderr', new_callable=StringIO)
    def test_quota_service_silence(self, mock_stderr, mock_stdout):
        mock_backend = ConcreteTestBackend()
        # Setup a dummy limit for the quota service to check against
        mock_backend.insert_usage_limit(MagicMock( # Use MagicMock for DTO
            scope=LimitScope.GLOBAL.value,
            limit_type=LimitType.REQUESTS.value,
            max_value=100,
            interval_unit=TimeInterval.DAY.value,
            interval_value=1,
            model=None, username=None, caller_name=None, project_name=None
        ))
        quota_service = QuotaService(backend=mock_backend)
        quota_service.check_quota(
            model="test_model",
            username="test_user",
            caller_name="test_caller",
            input_tokens=10,
            cost=0.01, # Added missing argument
            project_name="test_project" # Added missing argument
        )
        self.assertEqual(mock_stdout.getvalue(), "")
        self.assertEqual(mock_stderr.getvalue(), "")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('sys.stderr', new_callable=StringIO)
    def test_llm_accounting_context_manager_silence(self, mock_stderr, mock_stdout):
        # This test relies on the NullHandler in __init__.py to silence INFO logs
        # We need to temporarily set the library logger level to INFO to check
        # that the NullHandler is effective, as these are info logs.
        original_level = library_logger.level
        library_logger.setLevel(logging.INFO)
        # Ensure NullHandler is present as expected
        has_null_handler = any(isinstance(h, logging.NullHandler) for h in library_logger.handlers)
        if not has_null_handler:
             library_logger.addHandler(logging.NullHandler()) # Should be there from __init__

        with LLMAccounting(backend=ConcreteTestBackend()):
            pass # Operations inside the context

        library_logger.setLevel(original_level) # Restore level

        self.assertEqual(mock_stdout.getvalue(), "")
        self.assertEqual(mock_stderr.getvalue(), "")


    @patch('sys.stdout', new_callable=StringIO)
    @patch('sys.stderr', new_callable=StringIO)
    def test_mock_backend_operations_debug_silence(self, mock_stderr, mock_stdout):
        # The print() calls in mock_backend were replaced with logging.debug().
        # We need to ensure these debug logs are not printed if the level is INFO or higher.

        # Temporarily configure the mock_backend's specific loggers if they exist,
        # or rely on the main 'llm_accounting' logger's configuration.
        # For this test, let's ensure the 'llm_accounting' logger (parent of mock_backend loggers)
        # is set to INFO, so DEBUG messages shouldn't appear.
        original_level = library_logger.level
        library_logger.setLevel(logging.INFO) # Set to INFO
        library_logger.propagate = False # Prevent propagation for this specific test scenario

        # Remove all handlers and add a temporary StreamHandler to check if anything gets through
        # *if* logging was misconfigured (e.g. print was used instead of logging.debug)
        # This is a bit counter-intuitive: we're testing that print() is gone.
        # The NullHandler should prevent logging output. If print() was used, it would show up.

        # Resetting level to CRITICAL+1 as in setUp to ensure logging calls are silent
        library_logger.setLevel(logging.CRITICAL + 1)


        mock_backend = ConcreteTestBackend()
        mock_backend.initialize() # Had print, now logging.debug
        mock_backend.insert_usage(MagicMock(model="test")) # Had print, now logging.debug
        mock_backend.get_period_stats(datetime.now(), datetime.now()) # Had print, now logging.debug
        mock_backend.close() # Had print, now logging.debug

        library_logger.setLevel(original_level) # Restore

        self.assertEqual(mock_stdout.getvalue(), "")
        self.assertEqual(mock_stderr.getvalue(), "")

if __name__ == '__main__':
    unittest.main()
