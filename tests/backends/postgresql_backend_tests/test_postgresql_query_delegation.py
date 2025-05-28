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


class TestPostgreSQLQueryDelegation(BaseTestPostgreSQL):

    def test_get_period_stats_delegates_to_query_executor(self):
        self.backend.initialize()
        start_dt, end_dt = datetime(2023,1,1), datetime(2023,1,31)
        expected_stats = UsageStats(sum_cost=10.0)
        self.mock_query_executor_instance.get_period_stats.return_value = expected_stats
        
        stats = self.backend.get_period_stats(start_dt, end_dt)
        
        self.mock_query_executor_instance.get_period_stats.assert_called_once_with(start_dt, end_dt)
        self.assertEqual(stats, expected_stats)

    def test_get_model_stats_delegates_to_query_executor(self):
        self.backend.initialize()
        start_dt, end_dt = datetime(2023,1,1), datetime(2023,1,31)
        expected_model_stats = [("modelA", UsageStats(sum_cost=5.0))]
        self.mock_query_executor_instance.get_model_stats.return_value = expected_model_stats
        
        model_stats = self.backend.get_model_stats(start_dt, end_dt)
        
        self.mock_query_executor_instance.get_model_stats.assert_called_once_with(start_dt, end_dt)
        self.assertEqual(model_stats, expected_model_stats)
