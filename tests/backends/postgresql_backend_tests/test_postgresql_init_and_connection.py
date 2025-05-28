import unittest
from unittest.mock import patch, MagicMock, call
import os
from datetime import datetime, timezone

from src.llm_accounting.backends.postgresql import PostgreSQLBackend
from src.llm_accounting.backends.base import UsageEntry, UsageStats, AuditLogEntry
from src.llm_accounting.models.limits import UsageLimitDTO, LimitScope, LimitType, TimeInterval
from typing import List, Optional
from datetime import datetime, timezone, timedelta

import psycopg2

from tests.backends.postgresql_backend_tests.base_test_postgresql import BaseTestPostgreSQL


class TestPostgreSQLInitAndConnection(BaseTestPostgreSQL):

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
        with self.assertRaisesRegex(ConnectionError, r"Failed to connect to PostgreSQL database \(see logs for details\)\."):
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
