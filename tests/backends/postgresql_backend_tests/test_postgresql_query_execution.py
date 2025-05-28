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


class TestPostgreSQLQueryExecution(BaseTestPostgreSQL):

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
