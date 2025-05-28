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


class TestPostgreSQLUsageInsertion(BaseTestPostgreSQL):

    def test_insert_usage_success(self):
        self.backend.initialize()
        sample_entry = UsageEntry(model="gpt-4", cost=0.05, caller_name="")
        self.backend.insert_usage(sample_entry)
        self.mock_data_inserter_instance.insert_usage.assert_called_once_with(sample_entry)
