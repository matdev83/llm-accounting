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


class TestPostgreSQLQuotaAccounting(BaseTestPostgreSQL):

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
