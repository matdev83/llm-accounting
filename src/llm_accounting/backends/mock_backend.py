from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import logging

from .base import AuditLogEntry, BaseBackend, UsageEntry, UsageStats, UserRecord
from ..models.limits import LimitScope, LimitType, UsageLimitDTO

from .mock_backend_parts.connection_manager import MockConnectionManager
from .mock_backend_parts.usage_manager import MockUsageManager
from .mock_backend_parts.stats_manager import MockStatsManager
from .mock_backend_parts.query_executor import MockQueryExecutor
from .mock_backend_parts.limit_manager import MockLimitManager


# Removed redefinition of MockBackend, assuming the first definition is the correct one.


class MockBackend(BaseBackend):
    """
    A mock implementation of the BaseBackend for testing purposes.
    All operations are mocked to emulate positive results without actual database interaction.
    """

    def __init__(self):
        self.entries: List[UsageEntry] = []
        self.limits: List[UsageLimitDTO] = []
        self.next_limit_id: int = 1
        self.closed = False
        self.projects: List[str] = []
        self.users: List[str] = []

        self._connection_manager = MockConnectionManager(self)
        self._usage_manager = MockUsageManager(self)
        self._stats_manager = MockStatsManager(self)
        self._query_executor = MockQueryExecutor(self)
        self._limit_manager = MockLimitManager(self)

    def _ensure_connected(self) -> None:
        return self._connection_manager._ensure_connected()

    def initialize(self) -> None:
        return self._connection_manager.initialize()

    def insert_usage(self, entry: UsageEntry) -> None:
        return self._usage_manager.insert_usage(entry)

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return self._stats_manager.get_period_stats(start, end)

    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        return self._stats_manager.get_model_stats(start, end)

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, Any]]]:
        return self._stats_manager.get_model_rankings(start, end)

    def purge(self) -> None:
        return self._usage_manager.purge()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        return self._usage_manager.tail(n)

    def close(self) -> None:
        return self._connection_manager.close()

    def execute_query(self, query: str) -> list[dict]:
        return self._query_executor.execute_query(query)

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        return self._limit_manager.insert_usage_limit(limit)

    def delete_usage_limit(self, limit_id: int) -> None:
        return self._limit_manager.delete_usage_limit(limit_id)

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
        filter_username_null: Optional[bool] = None,
        filter_caller_name_null: Optional[bool] = None,
    ) -> List[UsageLimitDTO]:
        return self._limit_manager.get_usage_limits(
            scope, model, username, caller_name, project_name,
            filter_project_null, filter_username_null, filter_caller_name_null
        )

    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
    ) -> float:
        return self._limit_manager.get_accounting_entries_for_quota(
            start_time, limit_type, model, username, caller_name, project_name,
            filter_project_null
        )

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        return self._stats_manager.get_usage_costs(user_id, start_date, end_date)

    def initialize_audit_log_schema(self) -> None:
        """Mocks initializing the audit log schema."""
        logging.debug("MockBackend: Initializing audit log schema.")
        pass

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        """Mocks logging an audit event."""
        logging.debug(f"MockBackend: Logging audit event: {entry.log_type} for model {entry.model}")
        pass

    def get_audit_log_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        app_name: Optional[str] = None,
        user_name: Optional[str] = None,
        project: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AuditLogEntry]:
        """Mocks retrieving audit log entries."""
        logging.debug("MockBackend: Retrieving audit log entries.")
        # In a real mock, you might return a predefined list or filter stored entries
        return []

    # --- Project management ---

    def create_project(self, name: str) -> None:
        self.projects.append(name)

    def list_projects(self) -> List[str]:
        return list(self.projects)

    def update_project(self, name: str, new_name: str) -> None:
        if name in self.projects:
            self.projects[self.projects.index(name)] = new_name

    def delete_project(self, name: str) -> None:
        if name in self.projects:
            self.projects.remove(name)

    # --- User management ---

    def create_user(self, user_name: str, ou_name: Optional[str] = None, email: Optional[str] = None) -> None:
        self.users.append(user_name)

    def list_users(self) -> List[UserRecord]:
        return [UserRecord(user_name=u) for u in self.users]

    def update_user(
        self,
        user_name: str,
        new_user_name: Optional[str] = None,
        ou_name: Optional[str] = None,
        email: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        if user_name in self.users and new_user_name:
            idx = self.users.index(user_name)
            self.users[idx] = new_user_name

    def set_user_enabled(self, user_name: str, enabled: bool) -> None:
        pass
