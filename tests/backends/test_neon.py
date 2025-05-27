import unittest
from unittest.mock import patch, MagicMock, call
import os
from datetime import datetime

from src.llm_accounting.backends.neon import NeonBackend
from src.llm_accounting.backends.base import UsageEntry, UsageStats
# Updated imports: UsageLimitData and enums
from src.llm_accounting.models.limits import UsageLimitData, LimitScope, LimitType, TimeInterval

import psycopg2


class TestNeonBackend(unittest.TestCase):

    def setUp(self):
        self.patcher_psycopg2 = patch('src.llm_accounting.backends.neon_backend_parts.connection_manager.psycopg2')
        self.mock_psycopg2_module = self.patcher_psycopg2.start()

        class MockPsycopg2Error(Exception): pass
        self.mock_psycopg2_module.Error = MockPsycopg2Error
        self.mock_psycopg2_module.OperationalError = MockPsycopg2Error

        self.original_neon_conn_string = os.environ.get('NEON_CONNECTION_STRING')
        os.environ['NEON_CONNECTION_STRING'] = 'dummy_dsn_from_env'

        # Patch SchemaManager, DataInserter, DataDeleter, QueryExecutor, and LimitManager
        # These are instantiated within NeonBackend's __init__
        self.patcher_schema_manager = patch('src.llm_accounting.backends.neon.SchemaManager')
        self.mock_schema_manager_class = self.patcher_schema_manager.start()
        self.mock_schema_manager_instance = MagicMock(name="mock_schema_manager_instance")
        self.mock_schema_manager_class.return_value = self.mock_schema_manager_instance

        self.patcher_data_inserter = patch('src.llm_accounting.backends.neon.DataInserter')
        self.mock_data_inserter_class = self.patcher_data_inserter.start()
        self.mock_data_inserter_instance = MagicMock(name="mock_data_inserter_instance")
        self.mock_data_inserter_class.return_value = self.mock_data_inserter_instance
        
        # Mock for LimitManager (this is key for the tests being updated)
        self.patcher_limit_manager = patch('src.llm_accounting.backends.neon.LimitManager')
        self.mock_limit_manager_class = self.patcher_limit_manager.start()
        self.mock_limit_manager_instance = MagicMock(name="mock_limit_manager_instance")
        self.mock_limit_manager_class.return_value = self.mock_limit_manager_instance

        # Mocks for other managers if their methods are called directly by NeonBackend methods under test
        self.patcher_data_deleter = patch('src.llm_accounting.backends.neon.DataDeleter')
        self.mock_data_deleter_class = self.patcher_data_deleter.start()
        self.mock_data_deleter_instance = MagicMock(name="mock_data_deleter_instance")
        self.mock_data_deleter_class.return_value = self.mock_data_deleter_instance

        self.patcher_query_executor = patch('src.llm_accounting.backends.neon.QueryExecutor')
        self.mock_query_executor_class = self.patcher_query_executor.start()
        self.mock_query_executor_instance = MagicMock(name="mock_query_executor_instance")
        self.mock_query_executor_class.return_value = self.mock_query_executor_instance
        
        self.backend = NeonBackend()

        self.mock_conn = MagicMock(spec=psycopg2.extensions.connection) # Use spec for better mocking
        self.mock_psycopg2_module.connect.return_value = self.mock_conn
        self.mock_cursor = self.mock_conn.cursor.return_value.__enter__.return_value
        self.mock_conn.closed = False

    def tearDown(self):
        self.patcher_psycopg2.stop()
        self.patcher_schema_manager.stop()
        self.patcher_data_inserter.stop()
        self.patcher_limit_manager.stop() # Stop LimitManager patcher
        self.patcher_data_deleter.stop()
        self.patcher_query_executor.stop()

        if self.backend.conn and not self.backend.conn.closed:
            self.backend.conn.close()

        if self.original_neon_conn_string is None:
            if 'NEON_CONNECTION_STRING' in os.environ: del os.environ['NEON_CONNECTION_STRING']
        else:
            os.environ['NEON_CONNECTION_STRING'] = self.original_neon_conn_string

    def test_init_success(self):
        self.assertEqual(self.backend.connection_string, 'dummy_dsn_from_env')
        self.assertIsNone(self.backend.conn)
        # Check if managers are instantiated
        self.mock_schema_manager_class.assert_called_once_with(self.backend)
        self.mock_data_inserter_class.assert_called_once_with(self.backend)
        self.mock_limit_manager_class.assert_called_once_with(self.backend, self.mock_data_inserter_instance)


    def test_initialize_success(self):
        self.backend.initialize() # Calls connection_manager.initialize() and schema_manager._create_schema_if_not_exists()
        self.mock_psycopg2_module.connect.assert_called_once_with('dummy_dsn_from_env')
        self.assertEqual(self.backend.conn, self.mock_conn)
        self.mock_schema_manager_instance._create_schema_if_not_exists.assert_called_once()

    # ... (other tests like test_initialize_connection_error, test_close_connection remain similar) ...
    def test_initialize_connection_error(self):
        self.mock_psycopg2_module.connect.side_effect = self.mock_psycopg2_module.Error("Connection failed")
        with self.assertRaisesRegex(ConnectionError, r"Failed to connect to Neon/PostgreSQL database \(see logs for details\)\."):
            self.backend.initialize()
        self.assertIsNone(self.backend.conn)

    def test_close_connection(self):
        self.backend.initialize()
        self.assertEqual(self.backend.conn, self.mock_conn)
        self.backend.close()
        self.mock_conn.close.assert_called_once()
        self.assertIsNone(self.backend.conn)
        self.mock_conn.closed = True
        self.mock_conn.close.reset_mock()
        self.backend.close() 
        self.mock_conn.close.assert_not_called()
        self.assertIsNone(self.backend.conn)

    def test_insert_usage_success(self):
        self.backend.initialize()
        sample_entry = UsageEntry(model="gpt-4", cost=0.05, caller_name="")
        self.backend.insert_usage(sample_entry)
        # Check that DataInserter.insert_usage was called
        self.mock_data_inserter_instance.insert_usage.assert_called_once_with(sample_entry)

    # Refactored test for insert_usage_limit
    def test_insert_usage_limit_uses_limit_manager_with_usage_limit_data(self):
        self.backend.initialize() # Ensures _ensure_connected doesn't try to re-init in a way that breaks mocks

        test_limit_data = UsageLimitData(
            scope=LimitScope.USER.value,
            limit_type=LimitType.COST.value,
            max_value=100.0,
            interval_unit=TimeInterval.MONTH.value,
            interval_value=1,
            username="test_user_for_data",
            model="all_models_data"
            # created_at and updated_at can be None for new limits
        )
        self.backend.insert_usage_limit(test_limit_data)

        # Assert that LimitManager's insert_usage_limit was called with the UsageLimitData instance
        self.mock_limit_manager_instance.insert_usage_limit.assert_called_once_with(test_limit_data)
        # Ensure direct DB commit/rollback are not called by NeonBackend for this
        self.mock_conn.commit.assert_not_called()
        self.mock_conn.rollback.assert_not_called()


    # Refactored test for get_usage_limits
    def test_get_usage_limits_uses_limit_manager_and_returns_usage_limit_data(self):
        self.backend.initialize()

        mock_limit_data_list = [
            UsageLimitData(
                id=1, scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
                max_value=1000.0, interval_unit=TimeInterval.DAY.value, interval_value=1,
                created_at=datetime.now(), updated_at=datetime.now()
            ),
            UsageLimitData(
                id=2, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
                max_value=50.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
                username="user123", created_at=datetime.now(), updated_at=datetime.now()
            )
        ]
        # Configure the mock LimitManager to return this list
        self.mock_limit_manager_instance.get_usage_limits.return_value = mock_limit_data_list

        # Call get_usage_limits with some filter parameters
        filter_scope = LimitScope.USER
        filter_username = "user123"
        retrieved_limits = self.backend.get_usage_limits(scope=filter_scope, username=filter_username)

        # Assert that LimitManager's get_usage_limits was called with the correct filters
        self.mock_limit_manager_instance.get_usage_limits.assert_called_once_with(
            scope=filter_scope,
            model=None, # Not passed in this call
            username=filter_username,
            caller_name=None # Not passed in this call
        )
        
        self.assertEqual(retrieved_limits, mock_limit_data_list)
        self.assertIsInstance(retrieved_limits[0], UsageLimitData)
        self.assertIsInstance(retrieved_limits[1], UsageLimitData)
        # Ensure direct DB cursor execute is not called by NeonBackend for this
        self.mock_cursor.execute.assert_not_called()

    def test_delete_usage_limit_success(self):
        self.backend.initialize()
        limit_id_to_delete = 42
        self.backend.delete_usage_limit(limit_id_to_delete)
        # Check that DataDeleter.delete_usage_limit was called
        self.mock_data_deleter_instance.delete_usage_limit.assert_called_once_with(limit_id_to_delete)


    # --- Tests for methods delegated to QueryExecutor ---
    def test_get_period_stats_delegates_to_query_executor(self):
        self.backend.initialize()
        start_dt, end_dt = datetime(2023,1,1), datetime(2023,1,31)
        expected_stats = UsageStats(sum_cost=10.0)
        self.mock_query_executor_instance.get_period_stats.return_value = expected_stats
        
        stats = self.backend.get_period_stats(start_dt, end_dt)
        
        self.mock_query_executor_instance.get_period_stats.assert_called_once_with(start_dt, end_dt)
        self.assertEqual(stats, expected_stats)

    # ... (Similar delegation tests for get_model_stats, get_model_rankings, tail, get_usage_costs)

    def test_get_model_stats_delegates_to_query_executor(self):
        self.backend.initialize()
        start_dt, end_dt = datetime(2023,1,1), datetime(2023,1,31)
        expected_model_stats = [("modelA", UsageStats(sum_cost=5.0))]
        self.mock_query_executor_instance.get_model_stats.return_value = expected_model_stats
        
        model_stats = self.backend.get_model_stats(start_dt, end_dt)
        
        self.mock_query_executor_instance.get_model_stats.assert_called_once_with(start_dt, end_dt)
        self.assertEqual(model_stats, expected_model_stats)

    # --- Convenience methods (not part of BaseBackend but in NeonBackend) ---
    # These might need adjustments based on whether they use LimitManager or QueryExecutor now.
    # The previous version of NeonBackend had set_usage_limit and get_usage_limit calling QueryExecutor.
    # Let's assume they still do, or if they were meant to be part of the "limits" interface,
    # they should now also use LimitManager.
    # For now, let's assume they remain delegated to QueryExecutor as per the original structure
    # unless the subtask implies changing *all* limit-related methods.
    # The subtask was specific to insert_usage_limit and get_usage_limits (BaseBackend methods).

    def test_neon_specific_set_usage_limit_delegates_to_query_executor(self):
        self.backend.initialize()
        user_id = "test_user_specific"
        limit_amount = 300.0
        limit_type_str = "requests"
        
        # This is NeonBackend.set_usage_limit, not the BaseBackend one.
        self.backend.set_usage_limit(user_id, limit_amount, limit_type_str)
        
        self.mock_query_executor_instance.set_usage_limit.assert_called_once_with(user_id, limit_amount, limit_type_str)

    def test_neon_specific_get_usage_limit_delegates_to_limit_manager(self):
        # This convenience method was updated in NeonBackend to use LimitManager.
        self.backend.initialize()
        user_id = "user_specific_get"
        expected_data = [UsageLimitData(id=10, scope=LimitScope.USER.value, username=user_id, limit_type="cost", max_value=10, interval_unit="day", interval_value=1)]
        self.mock_limit_manager_instance.get_usage_limit.return_value = expected_data
        
        # This is NeonBackend.get_usage_limit (the specific one, not BaseBackend's get_usage_limits)
        result = self.backend.get_usage_limit(user_id)
        
        self.mock_limit_manager_instance.get_usage_limit.assert_called_once_with(user_id)
        self.assertEqual(result, expected_data)


if __name__ == '__main__':
    unittest.main()
