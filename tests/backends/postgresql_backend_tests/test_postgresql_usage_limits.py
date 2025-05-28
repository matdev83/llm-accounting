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


class TestPostgreSQLUsageLimits(BaseTestPostgreSQL):

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

    def test_delete_usage_limit_success(self):
        self.backend.initialize()
        limit_id_to_delete = 42
        self.backend.delete_usage_limit(limit_id_to_delete)
        self.mock_data_deleter_instance.delete_usage_limit.assert_called_once_with(limit_id_to_delete)

    def test_postgresql_specific_set_usage_limit_delegates_to_query_executor(self):
        self.backend.initialize()
        user_id = "test_user_specific"
        limit_amount = 300.0
        limit_type_str = "requests"
        
        # This is PostgreSQLBackend.set_usage_limit, not the BaseBackend one.
        self.backend.set_usage_limit(user_id, limit_amount, limit_type_str)
        
        self.mock_query_executor_instance.set_usage_limit.assert_called_once_with(user_id, limit_amount, limit_type_str)

    def test_postgresql_specific_get_usage_limit_delegates_to_limit_manager(self):
        # This convenience method was updated in PostgreSQLBackend to use LimitManager.
        self.backend.initialize()
        user_id = "user_specific_get"
        expected_data = [UsageLimitDTO(id=10, scope=LimitScope.USER.value, username=user_id, limit_type="cost", max_value=10, interval_unit="day", interval_value=1)]
        self.mock_limit_manager_instance.get_usage_limit.return_value = expected_data
        
        # This is PostgreSQLBackend.get_usage_limit (the specific one, not BaseBackend's get_usage_limits)
        result = self.backend.get_usage_limit(user_id)
        
        self.mock_limit_manager_instance.get_usage_limit.assert_called_once_with(user_id, project_name=None)
        self.assertEqual(result, expected_data)
