import unittest
from unittest.mock import patch, MagicMock
import os
import psycopg2 # Still needed for spec in MagicMock

class BaseTestPostgreSQL(unittest.TestCase):

    def setUp(self):
        # Patch the psycopg2 module used by ConnectionManager
        self.patcher_psycopg2 = patch('src.llm_accounting.backends.postgresql_backend_parts.connection_manager.psycopg2')
        self.mock_psycopg2_module = self.patcher_psycopg2.start()

        # Define mock exception classes that behave like psycopg2.Error
        class MockPsycopg2Error(Exception): pass
        self.mock_psycopg2_module.Error = MockPsycopg2Error
        self.mock_psycopg2_module.OperationalError = MockPsycopg2Error # Often a subclass of Error

        # Get the actual test PostgreSQL URL from the environment variable
        self.pg_url = os.environ.get('TEST_POSTGRESQL_DB_URL')

        if not self.pg_url:
            # If the environment variable is not set, skip this test.
            # This works with unittest.TestCase to skip the current test method.
            self.skipTest("TEST_POSTGRESQL_DB_URL environment variable not set. Skipping PostgreSQL backend test.")
            return  # Important to stop further setup

        # Store the original value of POSTGRESQL_CONNECTION_STRING (if any)
        # This is mainly for ensuring a clean environment after the test, as we pass the URL directly.
        self.original_env_postgresql_conn_string = os.environ.get('POSTGRESQL_CONNECTION_STRING')
        
        # Patch SchemaManager, DataInserter, DataDeleter, QueryExecutor, and LimitManager
        # These are instantiated within PostgreSQLBackend's __init__.
        # For some tests, we want to isolate PostgreSQLBackend's logic from these components.
        # For integration-style tests (e.g., testing schema creation), these mocks might be selectively disabled
        # or the tests might not use this base class if they need real components.
        self.patcher_schema_manager = patch('src.llm_accounting.backends.postgresql.SchemaManager')
        self.mock_schema_manager_class = self.patcher_schema_manager.start()
        self.mock_schema_manager_instance = MagicMock(name="mock_schema_manager_instance")
        self.mock_schema_manager_class.return_value = self.mock_schema_manager_instance

        self.patcher_data_inserter = patch('src.llm_accounting.backends.postgresql.DataInserter')
        self.mock_data_inserter_class = self.patcher_data_inserter.start()
        self.mock_data_inserter_instance = MagicMock(name="mock_data_inserter_instance")
        self.mock_data_inserter_class.return_value = self.mock_data_inserter_instance
        
        self.patcher_limit_manager = patch('src.llm_accounting.backends.postgresql.LimitManager')
        self.mock_limit_manager_class = self.patcher_limit_manager.start()
        self.mock_limit_manager_instance = MagicMock(name="mock_limit_manager_instance")
        self.mock_limit_manager_class.return_value = self.mock_limit_manager_instance

        self.patcher_data_deleter = patch('src.llm_accounting.backends.postgresql.DataDeleter')
        self.mock_data_deleter_class = self.patcher_data_deleter.start()
        self.mock_data_deleter_instance = MagicMock(name="mock_data_deleter_instance")
        self.mock_data_deleter_class.return_value = self.mock_data_deleter_instance

        self.patcher_query_executor = patch('src.llm_accounting.backends.postgresql.QueryExecutor')
        self.mock_query_executor_class = self.patcher_query_executor.start()
        self.mock_query_executor_instance = MagicMock(name="mock_query_executor_instance")
        self.mock_query_executor_class.return_value = self.mock_query_executor_instance
        
        # Import PostgreSQLBackend here to avoid potential import loops if it imports managers at module level
        from src.llm_accounting.backends.postgresql import PostgreSQLBackend
        # Instantiate the backend, passing the connection string directly.
        # PostgreSQLBackend's __init__ prioritizes the direct argument over the env var.
        self.backend = PostgreSQLBackend(postgresql_connection_string=self.pg_url)

        # Mock the connection object that would be created by ConnectionManager
        self.mock_conn = MagicMock(spec=psycopg2.extensions.connection) # Use psycopg2.extensions.connection if available
        self.mock_psycopg2_module.connect.return_value = self.mock_conn
        self.mock_cursor = self.mock_conn.cursor.return_value.__enter__.return_value # For 'with backend.conn.cursor() as cur:'
        self.mock_conn.closed = False # Simulate an open connection initially

    def tearDown(self):
        # Stop all patchers
        self.patcher_psycopg2.stop()
        self.patcher_schema_manager.stop()
        self.patcher_data_inserter.stop()
        self.patcher_limit_manager.stop()
        self.patcher_data_deleter.stop()
        self.patcher_query_executor.stop()

        # Close the backend's connection if it was initialized and opened
        # self.backend might not exist if setUp was skipped.
        if hasattr(self, 'backend') and self.backend:
            # The backend's psycopg2 connection is self.backend.conn
            # The backend's SQLAlchemy engine is self.backend.engine
            if self.backend.conn and not self.backend.conn.closed:
                 # This conn is the psycopg2 connection if ConnectionManager initialized it.
                 # If tests involve real DB interactions, this conn would be real.
                 # The mock_conn above is for isolating ConnectionManager's direct psycopg2 usage.
                 # PostgreSQLBackend.close() handles closing its own psycopg2 conn and disposing engine.
                self.backend.close() 
            elif self.backend.engine: # If only engine was created but not psycopg2 conn
                self.backend.close()


        # Restore the original POSTGRESQL_CONNECTION_STRING environment variable, if it was set.
        # This check needs to access the attribute set in setUp.
        if hasattr(self, 'original_env_postgresql_conn_string'):
            if self.original_env_postgresql_conn_string is None:
                # If it was originally not set, remove it if it somehow got set (should not happen with current logic).
                os.environ.pop('POSTGRESQL_CONNECTION_STRING', None)
            else:
                # If it was originally set, restore its value.
                os.environ['POSTGRESQL_CONNECTION_STRING'] = self.original_env_postgresql_conn_string
            delattr(self, 'original_env_postgresql_conn_string') # Clean up instance attribute
        
        # Clean up pg_url attribute
        if hasattr(self, 'pg_url'):
            delattr(self, 'pg_url')
