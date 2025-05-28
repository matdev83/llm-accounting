import unittest
from unittest.mock import patch, MagicMock, call
import os
from datetime import datetime, timezone, timedelta

from src.llm_accounting.backends.postgresql import PostgreSQLBackend
from src.llm_accounting.backends.base import UsageEntry, UsageStats, AuditLogEntry
from src.llm_accounting.models.limits import UsageLimitDTO, LimitScope, LimitType, TimeInterval
from typing import List, Optional

import psycopg2

from tests.backends.postgresql_backend_tests.base_test_postgresql import BaseTestPostgreSQL


class TestPostgreSQLAuditLog(BaseTestPostgreSQL):

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
        
        with self.assertRaisesRegex(RuntimeError, r"Failed to log audit event due to database error: DB error on insert"):
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
