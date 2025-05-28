import unittest
from unittest.mock import patch, MagicMock, call
import os
from datetime import datetime, timezone

from src.llm_accounting.backends.neon import NeonBackend
from src.llm_accounting.backends.base import UsageEntry, UsageStats, AuditLogEntry # Added AuditLogEntry
from src.llm_accounting.models.limits import UsageLimitDTO, LimitScope, LimitType, TimeInterval
from typing import List, Optional
from datetime import datetime, timezone, timedelta # Import timedelta

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

        if self.original_neon_conn_string is None:
            if 'NEON_CONNECTION_STRING' in os.environ: del os.environ['NEON_CONNECTION_STRING']
        else:
            os.environ['NEON_CONNECTION_STRING'] = self.original_neon_conn_string

    def test_init_success(self):
        self.assertEqual(self.backend.connection_string, 'dummy_dsn_from_env')
        self.assertIsNone(self.backend.conn)
        self.mock_schema_manager_class.assert_called_once_with(self.backend)
        self.mock_data_inserter_class.assert_called_once_with(self.backend)
        self.mock_limit_manager_class.assert_called_once_with(self.backend, self.mock_data_inserter_instance)


    def test_initialize_success(self):
        self.backend.initialize()
        self.mock_psycopg2_module.connect.assert_called_once_with('dummy_dsn_from_env')
        self.assertEqual(self.backend.conn, self.mock_conn)
        self.mock_schema_manager_instance._create_schema_if_not_exists.assert_called_once()

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
        self.mock_data_inserter_instance.insert_usage.assert_called_once_with(sample_entry)

    def test_insert_usage_limit_uses_limit_manager_with_usage_limit_data(self):
        self.backend.initialize()

        test_limit_data = UsageLimitDTO(
            scope=LimitScope.USER.value,
            limit_type=LimitType.COST.value,
            max_value=100.0,
            interval_unit=TimeInterval.MONTH.value,
            interval_value=1,
            username="test_user_for_data",
            model="all_models_data"
        )
        self.backend.insert_usage_limit(test_limit_data)

        self.mock_limit_manager_instance.insert_usage_limit.assert_called_once_with(test_limit_data)
        self.mock_conn.commit.assert_not_called()
        self.mock_conn.rollback.assert_not_called()


    def test_get_usage_limits_uses_limit_manager_and_returns_usage_limit_data(self):
        self.backend.initialize()

        mock_limit_data_list = [
            UsageLimitDTO(
                id=1, scope=LimitScope.GLOBAL.value, limit_type=LimitType.REQUESTS.value,
                max_value=1000.0, interval_unit=TimeInterval.DAY.value, interval_value=1,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
            ),
            UsageLimitDTO(
                id=2, scope=LimitScope.USER.value, limit_type=LimitType.COST.value,
                max_value=50.0, interval_unit=TimeInterval.MONTH.value, interval_value=1,
                username="user123", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
            )
        ]
        self.mock_limit_manager_instance.get_usage_limits.return_value = mock_limit_data_list

        filter_scope = LimitScope.USER
        filter_username = "user123"
        retrieved_limits = self.backend.get_usage_limits(scope=filter_scope, username=filter_username)

        self.mock_limit_manager_instance.get_usage_limits.assert_called_once_with(
            scope=filter_scope,
            model=None,
            username=filter_username,
            caller_name=None,
            project_name=None,
            filter_project_null=None,
            filter_username_null=None,
            filter_caller_name_null=None
        )
        
        self.assertEqual(retrieved_limits, mock_limit_data_list)
        self.assertIsInstance(retrieved_limits[0], UsageLimitDTO)
        self.assertIsInstance(retrieved_limits[1], UsageLimitDTO)
        self.mock_cursor.execute.assert_not_called()


    def test_get_accounting_entries_for_quota_success(self):
        self.backend.initialize()
        start_time = datetime(2023, 1, 1, 0, 0, 0)

        self.mock_cursor.fetchone.return_value = (123.45,)
        cost_val = self.backend.get_accounting_entries_for_quota(start_time, LimitType.COST, model='gpt-4', project_name='projA')
        self.mock_cursor.execute.assert_called_with(
            "SELECT COALESCE(SUM(cost), 0.0) AS aggregated_value FROM accounting_entries WHERE timestamp >= %s AND model_name = %s AND project = %s;",
            (start_time, 'gpt-4', 'projA')
        )
        self.assertEqual(cost_val, 123.45)

        self.mock_cursor.fetchone.return_value = (50,)
        requests_val = self.backend.get_accounting_entries_for_quota(start_time, LimitType.REQUESTS, username='user1', project_name=None, filter_project_null=True)
        self.mock_cursor.execute.assert_called_with(
            "SELECT COUNT(*) AS aggregated_value FROM accounting_entries WHERE timestamp >= %s AND username = %s AND project IS NULL;",
            (start_time, 'user1')
        )
        self.assertEqual(requests_val, 50)
        
        self.mock_cursor.fetchone.return_value = (10000,)
        input_tokens_val = self.backend.get_accounting_entries_for_quota(start_time, LimitType.INPUT_TOKENS, caller_name='caller_A', project_name='projB')
        self.mock_cursor.execute.assert_called_with(
            "SELECT COALESCE(SUM(prompt_tokens), 0) AS aggregated_value FROM accounting_entries WHERE timestamp >= %s AND caller_name = %s AND project = %s;",
            (start_time, 'caller_A', 'projB')
        )
        self.assertEqual(input_tokens_val, 10000)

        self.mock_cursor.fetchone.return_value = (20000,)
        output_tokens_val = self.backend.get_accounting_entries_for_quota(start_time, LimitType.OUTPUT_TOKENS, caller_name='caller_B', project_name='projC')
        self.mock_cursor.execute.assert_called_with(
            "SELECT COALESCE(SUM(completion_tokens), 0) AS aggregated_value FROM accounting_entries WHERE timestamp >= %s AND caller_name = %s AND project = %s;",
            (start_time, 'caller_B', 'projC')
        )
        self.assertEqual(output_tokens_val, 20000)

    def test_get_accounting_entries_for_quota_no_data(self):
        self.backend.initialize()
        self.mock_cursor.fetchone.return_value = (0.0,)
        val = self.backend.get_accounting_entries_for_quota(datetime.now(), LimitType.COST)
        self.assertEqual(val, 0.0)
        
        self.mock_cursor.fetchone.return_value = (0,)
        val_tokens = self.backend.get_accounting_entries_for_quota(datetime.now(), LimitType.INPUT_TOKENS)
        self.assertEqual(val_tokens, 0)


    def test_get_accounting_entries_for_quota_db_error(self):
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Quota check failed")
        with self.assertRaises(psycopg2.Error):
            self.backend.get_accounting_entries_for_quota(datetime.now(), LimitType.COST)

    def test_get_accounting_entries_for_quota_invalid_type(self):
        self.backend.initialize()
        with self.assertRaisesRegex(ValueError, "'unsupported' is not a valid LimitType"):
            self.backend.get_accounting_entries_for_quota(datetime.now(), LimitType("unsupported"))


    def test_execute_query_success(self):
        self.backend.initialize()
        raw_query_for_execute = "SELECT * FROM accounting_entries WHERE cost > 10;"
        expected_result = [{'id': 1, 'cost': 20.0}, {'id': 2, 'cost': 30.0}]
        self.mock_cursor.fetchall.return_value = expected_result
        
        result = self.backend.execute_query(raw_query_for_execute)

        self.mock_cursor.execute.assert_called_once_with(raw_query_for_execute)
        self.assertEqual(result, expected_result)

    def test_execute_query_non_select_error(self):
        self.backend.initialize()
        non_select_query = "DELETE FROM accounting_entries;"
        with self.assertRaisesRegex(ValueError, "Only SELECT queries are allowed"):
            self.backend.execute_query(non_select_query)
        self.mock_cursor.execute.assert_not_called()

    def test_delete_usage_limit_success(self):
        self.backend.initialize()
        limit_id_to_delete = 42
        self.backend.delete_usage_limit(limit_id_to_delete)
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
        expected_data = [UsageLimitDTO(id=10, scope=LimitScope.USER.value, username=user_id, limit_type="cost", max_value=10, interval_unit="day", interval_value=1)]
        self.mock_limit_manager_instance.get_usage_limit.return_value = expected_data
        
        # This is NeonBackend.get_usage_limit (the specific one, not BaseBackend's get_usage_limits)
        result = self.backend.get_usage_limit(user_id)
        
        self.mock_limit_manager_instance.get_usage_limit.assert_called_once_with(user_id, project_name=None)
        self.assertEqual(result, expected_data)

    # --- Audit Log Functionality Tests ---

    def test_initialize_creates_audit_log_table(self):
        """
        Tests that initialize calls SchemaManager._create_schema_if_not_exists,
        which is responsible for all table creations including audit_log_entries.
        """
        self.backend.initialize() # This calls _create_schema_if_not_exists
        self.mock_schema_manager_instance._create_schema_if_not_exists.assert_called_once()
        # Further verification that _create_schema_if_not_exists itself calls _create_tables
        # which then includes the audit log DDL would be part of SchemaManager's own tests.
        # Here we confirm NeonBackend delegates overall schema setup.

    def test_initialize_audit_log_schema_method_ensures_connection(self):
        """
        Tests the specific initialize_audit_log_schema method.
        It should ensure connection. Schema creation is handled by the main initialize.
        """
        # Reset mocks that might have been called during self.backend instantiation or previous calls
        self.mock_psycopg2_module.connect.reset_mock()
        
        # Simulate connection not being active initially
        self.backend.conn = None
        
        self.backend.initialize_audit_log_schema()
        
        # Check if connection_manager.ensure_connected (which calls psycopg2.connect if conn is None) was triggered
        self.mock_psycopg2_module.connect.assert_called_once_with('dummy_dsn_from_env')
        self.assertEqual(self.backend.conn, self.mock_conn)
        # Also check that _create_schema_if_not_exists is NOT called by this specific method,
        # as it's handled by the main initialize().
        self.mock_schema_manager_instance._create_schema_if_not_exists.assert_not_called()


    def test_log_audit_event_delegates_and_manages_transaction(self):
        """
        Tests that log_audit_event delegates to DataInserter and manages transactions.
        """
        self.backend.initialize() # Ensure connection is set up
        
        sample_entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            app_name="test_app",
            user_name="test_user",
            model="test_model",
            log_type="test_log",
            id=None, # id is managed by DB
            prompt_text=None, response_text=None, remote_completion_id=None, project=None
        )
        self.backend.log_audit_event(sample_entry)

        self.mock_data_inserter_instance.insert_audit_log_event.assert_called_once_with(sample_entry)
        self.mock_conn.commit.assert_called_once()
        self.mock_conn.rollback.assert_not_called()

        # Test rollback on DataInserter failure
        self.mock_data_inserter_instance.reset_mock()
        self.mock_conn.reset_mock()
        self.mock_data_inserter_instance.insert_audit_log_event.side_effect = self.mock_psycopg2_module.Error("DB error on insert")
        
        with self.assertRaisesRegex(RuntimeError, "Unexpected error occurred while logging audit event: DB error on insert"):
            self.backend.log_audit_event(sample_entry)
        
        self.mock_data_inserter_instance.insert_audit_log_event.assert_called_once_with(sample_entry)
        self.mock_conn.commit.assert_not_called()
        self.mock_conn.rollback.assert_called_once()

    def test_get_audit_log_entries_delegates_to_query_executor(self):
        """
        Tests that get_audit_log_entries delegates to QueryExecutor.
        """
        self.backend.initialize() # Ensure connection is set up

        now = datetime.now(timezone.utc)
        expected_entries_data = [
            AuditLogEntry(timestamp=now, app_name="app1", user_name="user1", model="model1", log_type="type1", id=1, prompt_text=None, response_text=None, remote_completion_id=None, project=None),
            AuditLogEntry(timestamp=now, app_name="app2", user_name="user2", model="model2", log_type="type2", id=2, prompt_text=None, response_text=None, remote_completion_id=None, project=None)
        ]
        self.mock_query_executor_instance.get_audit_log_entries.return_value = expected_entries_data

        filter_params = {
            "start_date": now - timedelta(days=1),
            "end_date": now,
            "app_name": "test_app_filter",
            "user_name": "test_user_filter",
            "project": "TestProject",
            "log_type": "test_type_filter",
            "limit": 50
        }
        
        retrieved_entries = self.backend.get_audit_log_entries(**filter_params)

        self.mock_query_executor_instance.get_audit_log_entries.assert_called_once_with(**filter_params)
        self.assertEqual(retrieved_entries, expected_entries_data)

        # Test with no filters
        self.mock_query_executor_instance.reset_mock()
        expected_empty_call_entries = [AuditLogEntry(timestamp=now, app_name="app3", user_name="user3", model="model3", log_type="type3", id=3, prompt_text=None, response_text=None, remote_completion_id=None, project=None)]
        self.mock_query_executor_instance.get_audit_log_entries.return_value = expected_empty_call_entries

        retrieved_no_filters = self.backend.get_audit_log_entries()
        self.mock_query_executor_instance.get_audit_log_entries.assert_called_once_with(
            start_date=None, end_date=None, app_name=None, user_name=None,
            project=None, log_type=None, limit=None
        )
        self.assertEqual(retrieved_no_filters, expected_empty_call_entries)


if __name__ == '__main__':
    unittest.main()
