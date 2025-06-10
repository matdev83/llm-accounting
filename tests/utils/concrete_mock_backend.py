from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from llm_accounting.backends.base import (
    BaseBackend,
    AuditLogEntry,
    UsageEntry,
    UsageStats,
    UserRecord,
)
from llm_accounting.models.limits import LimitScope, LimitType, UsageLimitDTO


class ConcreteTestBackend(BaseBackend):
    """A concrete implementation of BaseBackend for testing purposes."""
    def initialize(self) -> None:
        pass
    def insert_usage(self, entry: UsageEntry) -> None:
        pass
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return UsageStats()
    def get_model_stats(self, start: datetime, end: datetime) -> list[tuple[str, UsageStats]]:
        return []
    def get_model_rankings(self, start: datetime, end: datetime) -> dict[str, list[tuple[str, Any]]]:
        return {}
    def purge(self) -> None:
        pass
    def tail(self, n: int = 10) -> list[UsageEntry]:
        return []
    def close(self) -> None:
        pass
    def execute_query(self, query: str) -> list[dict]:
        return []
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
        return 0.0
    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        pass
    def delete_usage_limit(self, limit_id: int) -> None:
        pass
    def _ensure_connected(self) -> None:
        pass
    def initialize_audit_log_schema(self) -> None:
        pass
    def log_audit_event(self, entry: AuditLogEntry) -> None:
        pass

    def log_quota_rejection(self, session: str, rejection_message: str, created_at: Optional[datetime] = None) -> None:
        pass
    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        return 0.0
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
        return []

    # project management
    def create_project(self, name: str) -> None:
        pass

    def list_projects(self) -> List[str]:
        return []

    def update_project(self, name: str, new_name: str) -> None:
        pass

    def delete_project(self, name: str) -> None:
        pass

    # user management
    def create_user(self, user_name: str, ou_name: Optional[str] = None, email: Optional[str] = None) -> None:
        pass

    def list_users(self) -> List[UserRecord]:
        return []

    def update_user(
        self,
        user_name: str,
        new_user_name: Optional[str] = None,
        ou_name: Optional[str] = None,
        email: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        pass

    def set_user_enabled(self, user_name: str, enabled: bool) -> None:
        pass
