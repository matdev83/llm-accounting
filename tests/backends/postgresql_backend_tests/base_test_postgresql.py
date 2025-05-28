import unittest
from unittest.mock import patch, MagicMock
import os
import psycopg2

class BaseTestPostgreSQL(unittest.TestCase):

    def setUp(self):
        self.patcher_psycopg2 = patch('src.llm_accounting.backends.postgresql_backend_parts.connection_manager.psycopg2')
        self.mock_psycopg2_module = self.patcher_psycopg2.start()

        class MockPsycopg2Error(Exception): pass
        self.mock_psycopg2_module.Error = MockPsycopg2Error
        self.mock_psycopg2_module.OperationalError = MockPsycopg2Error

        self.original_postgresql_conn_string = os.environ.get('POSTGRESQL_CONNECTION_STRING')
        os.environ['POSTGRESQL_CONNECTION_STRING'] = 'dummy_dsn_from_env'

        # Patch SchemaManager, DataInserter, DataDeleter, QueryExecutor, and LimitManager
        # These are instantiated within PostgreSQLBackend's __init__
        self.patcher_schema_manager = patch('src.llm_accounting.backends.postgresql.SchemaManager')
        self.mock_schema_manager_class = self.patcher_schema_manager.start()
        self.mock_schema_manager_instance = MagicMock(name="mock_schema_manager_instance")
        self.mock_schema_manager_class.return_value = self.mock_schema_manager_instance

        self.patcher_data_inserter = patch('src.llm_accounting.backends.postgresql.DataInserter')
        self.mock_data_inserter_class = self.patcher_data_inserter.start()
        self.mock_data_inserter_instance = MagicMock(name="mock_data_inserter_instance")
        self.mock_data_inserter_class.return_value = self.mock_data_inserter_instance
        
        # Mock for LimitManager (this is key for the tests being updated)
        self.patcher_limit_manager = patch('src.llm_accounting.backends.postgresql.LimitManager')
        self.mock_limit_manager_class = self.patcher_limit_manager.start()
        self.mock_limit_manager_instance = MagicMock(name="mock_limit_manager_instance")
        self.mock_limit_manager_class.return_value = self.mock_limit_manager_instance

        # Mocks for other managers if their methods are called directly by PostgreSQLBackend methods under test
        self.patcher_data_deleter = patch('src.llm_accounting.backends.postgresql.DataDeleter')
        self.mock_data_deleter_class = self.patcher_data_deleter.start()
        self.mock_data_deleter_instance = MagicMock(name="mock_data_deleter_instance")
        self.mock_data_deleter_class.return_value = self.mock_data_deleter_instance

        self.patcher_query_executor = patch('src.llm_accounting.backends.postgresql.QueryExecutor')
        self.mock_query_executor_class = self.patcher_query_executor.start()
        self.mock_query_executor_instance = MagicMock(name="mock_query_executor_instance")
        self.mock_query_executor_class.return_value = self.mock_query_executor_instance
        
        # Import PostgreSQLBackend here to avoid circular dependency issues if it imports from managers
        from src.llm_accounting.backends.postgresql import PostgreSQLBackend
        self.backend = PostgreSQLBackend()

        self.mock_conn = MagicMock(spec=psycopg2.extensions.connection)
        self.mock_psycopg2_module.connect.return_value = self.mock_conn
        self.mock_cursor = self.mock_conn.cursor.return_value.__enter__.return_value
        self.mock_conn.closed = False

    def tearDown(self):
        self.patcher_psycopg2.stop()
        self.patcher_schema_manager.stop()
        self.patcher_data_inserter.stop()
        self.patcher_limit_manager.stop()
        self.patcher_data_deleter.stop()
        self.patcher_query_executor.stop()

        if self.backend.conn and not self.backend.conn.closed:
            self.backend.conn.close()

        if self.original_postgresql_conn_string is None:
            if 'POSTGRESQL_CONNECTION_STRING' in os.environ: del os.environ['POSTGRESQL_CONNECTION_STRING']
        else:
            os.environ['POSTGRESQL_CONNECTION_STRING'] = self.original_postgresql_conn_string
