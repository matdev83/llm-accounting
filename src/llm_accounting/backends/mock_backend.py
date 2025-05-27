from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import override

from .base import BaseBackend, UsageEntry, UsageStats
from ..models.limits import LimitScope, LimitType, UsageLimitDTO

from .mock_backend_parts.connection_manager import MockConnectionManager
from .mock_backend_parts.usage_manager import MockUsageManager
from .mock_backend_parts.stats_manager import MockStatsManager
from .mock_backend_parts.query_executor import MockQueryExecutor
from .mock_backend_parts.limit_manager import MockLimitManager


class MockBackend(BaseBackend):
    """
    A mock implementation of the BaseBackend for testing purposes.
    All operations are mocked to emulate positive results without actual database interaction.
    """

    def __init__(self):
        self.entries: List[UsageEntry] = []
        self.limits: List[UsageLimitDTO] = []
        self.next_limit_id: int = 1
        self.initialized = False
        self.closed = False

        self._connection_manager = MockConnectionManager(self)
        self._usage_manager = MockUsageManager(self)
        self._stats_manager = MockStatsManager(self)
        self._query_executor = MockQueryExecutor(self)
        self._limit_manager = MockLimitManager(self)

    @override
    def _ensure_connected(self) -> None:
        return self._connection_manager._ensure_connected()

    @override
    def initialize(self) -> None:
        return self._connection_manager.initialize()

    @override
    def insert_usage(self, entry: UsageEntry) -> None:
        return self._usage_manager.insert_usage(entry)

    @override
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return self._stats_manager.get_period_stats(start, end)

    @override
    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        return self._stats_manager.get_model_stats(start, end)

    @override
    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, Any]]]:
        return self._stats_manager.get_model_rankings(start, end)

    @override
    def purge(self) -> None:
        return self._usage_manager.purge()

    @override
    def tail(self, n: int = 10) -> List[UsageEntry]:
        return self._usage_manager.tail(n)

    @override
    def close(self) -> None:
        return self._connection_manager.close()

    @override
    def execute_query(self, query: str) -> list[dict]:
        return self._query_executor.execute_query(query)

    @override
    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        return self._limit_manager.insert_usage_limit(limit)

    @override
    def delete_usage_limit(self, limit_id: int) -> None:
        return self._limit_manager.delete_usage_limit(limit_id)

    @override
    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = False,
        filter_username_null: Optional[bool] = False,
        filter_caller_name_null: Optional[bool] = False,
    ) -> List[UsageLimitDTO]:
        return self._limit_manager.get_usage_limits(
            scope, model, username, caller_name, project_name,
            filter_project_null, filter_username_null, filter_caller_name_null
        )

    @override
    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = False,
    ) -> float:
        return self._limit_manager.get_accounting_entries_for_quota(
            start_time, limit_type, model, username, caller_name, project_name,
            filter_project_null
        )

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        return self._stats_manager.get_usage_costs(user_id, start_date, end_date)
