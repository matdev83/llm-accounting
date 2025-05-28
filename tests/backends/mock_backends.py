from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import override


from llm_accounting.backends.base import BaseBackend, UsageEntry, UsageStats
from llm_accounting.models.limits import LimitScope, LimitType, UsageLimitDTO


class MockBackend(BaseBackend):
    """A mock backend that implements all required methods for BaseBackend interface testing."""

    @override
    def _ensure_connected(self) -> None:
        """Mocks ensuring connection."""
        pass

    @override
    def initialize(self) -> None:
        pass

    @override
    def insert_usage(self, entry: UsageEntry) -> None:
        pass

    @override
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return UsageStats()

    @override
    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        return []

    @override
    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        return {}

    @override
    def purge(self) -> None:
        pass

    @override
    def tail(self, n: int = 10) -> List[UsageEntry]:
        return []

    @override
    def close(self) -> None:
        pass

    @override
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Mock implementation of execute_query"""
        if query.strip().upper().startswith("SELECT"):
            return [{}] 
        raise ValueError("MockBackend in test_base.py only supports SELECT for execute_query.")


    @override
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
        return []

    @override
    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None # New parameter
    ) -> float:
        return 0.0

    @override
    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        pass

    @override
    def delete_usage_limit(self, limit_id: int) -> None:
        pass

    @override
    def initialize_audit_log_schema(self) -> None:
        pass

    @override
    def log_audit_event(self, entry: Any) -> None: # Using Any for entry to avoid circular import for AuditLogEntry
        pass

    @override
    def get_audit_log_entries(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, app_name: Optional[str] = None, user_name: Optional[str] = None, project: Optional[str] = None, log_type: Optional[str] = None, limit: Optional[int] = None) -> List[Any]: # Using Any for AuditLogEntry
        return []


class IncompleteBackend(BaseBackend):
    """A mock backend that doesn't implement all required methods for BaseBackend interface testing."""

    def initialize(self) -> None:
        pass

    @override
    def _ensure_connected(self) -> None: pass
    @override
    def insert_usage(self, entry: UsageEntry) -> None: pass
    @override
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats: return UsageStats()
    @override
    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]: return []
    @override
    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]: return {}
    @override
    def purge(self) -> None: pass
    @override
    def tail(self, n: int = 10) -> List[UsageEntry]: return []
    @override
    def close(self) -> None: pass
    @override
    def execute_query(self, query: str) -> List[Dict[str, Any]]: return [{}]
    @override
    def get_usage_limits(self, scope: Optional[LimitScope] = None, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None, project_name: Optional[str] = None, filter_project_null: Optional[bool] = None, filter_username_null: Optional[bool] = None, filter_caller_name_null: Optional[bool] = None) -> List[UsageLimitDTO]: return []
    @override
    def get_accounting_entries_for_quota(self, start_time: datetime, limit_type: LimitType, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None, project_name: Optional[str] = None, filter_project_null: Optional[bool] = None) -> float: return 0.0
    @override
    def insert_usage_limit(self, limit: UsageLimitDTO) -> None: pass

    @override
    def initialize_audit_log_schema(self) -> None: pass

    @override
    def log_audit_event(self, entry: Any) -> None: pass

    @override
    def get_audit_log_entries(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, app_name: Optional[str] = None, user_name: Optional[str] = None, project: Optional[str] = None, log_type: Optional[str] = None, limit: Optional[int] = None) -> List[Any]: return []
