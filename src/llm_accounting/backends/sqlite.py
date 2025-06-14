import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import text
from ..models.limits import LimitScope, LimitType, UsageLimitDTO
from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry, UserRecord
from .sqlite_utils import validate_db_filename
from .sqlite_backend_parts.connection_manager import SQLiteConnectionManager
from .sqlite_backend_parts.query_executor import SQLiteQueryExecutor
from .sqlite_backend_parts.usage_manager import SQLiteUsageManager
from .sqlite_backend_parts.limit_manager import SQLiteLimitManager
from .sqlite_backend_parts.audit_log_manager import SQLiteAuditLogManager
from .sqlite_backend_parts.quota_rejection_manager import SQLiteQuotaRejectionManager
from .sqlite_backend_parts.project_manager import SQLiteProjectManager
from .sqlite_backend_parts.user_manager import SQLiteUserManager

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/accounting.sqlite"


class SQLiteBackend(BaseBackend):
    def __init__(self, db_path: Optional[str] = None):
        actual_db_path = db_path if db_path is not None else DEFAULT_DB_PATH
        validate_db_filename(actual_db_path)
        self.db_path = actual_db_path
        if not self.db_path.startswith("file:") and self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection_manager = SQLiteConnectionManager(self.db_path, DEFAULT_DB_PATH)
        self.query_executor = SQLiteQueryExecutor(self.connection_manager)
        self.usage_manager = SQLiteUsageManager(self.connection_manager)
        self.limit_manager = SQLiteLimitManager(self.connection_manager)
        self.audit_log_manager = SQLiteAuditLogManager(self.connection_manager)
        self.project_manager = SQLiteProjectManager(self.connection_manager)
        self.user_manager = SQLiteUserManager(self.connection_manager)
        self.quota_rejection_manager = SQLiteQuotaRejectionManager(self.connection_manager)

    def initialize(self) -> None:
        self.connection_manager.initialize()

    def insert_usage(self, entry: UsageEntry) -> None:
        """Insert a new usage entry into the database"""
        conn = self.connection_manager.get_connection()
        self.usage_manager.insert_usage(conn, entry)
        conn.commit()

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        conn = self.connection_manager.get_connection()
        return self.usage_manager.get_period_stats(conn, start, end)

    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        """Get statistics grouped by model for a time period"""
        conn = self.connection_manager.get_connection()
        return self.usage_manager.get_model_stats(conn, start, end)

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        conn = self.connection_manager.get_connection()
        return self.usage_manager.get_model_rankings(conn, start, end)

    def purge(self) -> None:
        """Delete all usage entries from the database"""
        conn = self.connection_manager.get_connection()
        conn.execute(text("DELETE FROM accounting_entries"))
        conn.execute(text("DELETE FROM usage_limits"))
        conn.execute(text("DELETE FROM audit_log_entries"))
        conn.commit()

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """Insert a new usage limit entry into the database."""
        self.limit_manager.insert_usage_limit(limit)

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        conn = self.connection_manager.get_connection()
        return self.usage_manager.tail(conn, n)

    def close(self) -> None:
        """Close the SQLAlchemy database connection"""
        self.connection_manager.close()

    def execute_query(self, query: str) -> List[Dict]:
        """
        Execute a raw SQL SELECT query and return results.
        """
        return self.query_executor.execute_query(query)

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
        return self.limit_manager.get_usage_limits(
            scope, model, username, caller_name, project_name,
            filter_project_null, filter_username_null, filter_caller_name_null
        )

    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        end_time: datetime,
        limit_type: LimitType,
        interval_unit: Any,  # Add interval_unit parameter
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
    ) -> float:
        conn = self.connection_manager.get_connection()
        return self.usage_manager.get_accounting_entries_for_quota(
            conn, start_time, end_time, limit_type, interval_unit, model, username, caller_name, project_name, filter_project_null
        )

    def delete_usage_limit(self, limit_id: int) -> None:
        """Delete a usage limit entry by its ID."""
        self.limit_manager.delete_usage_limit(limit_id)

    def _ensure_connected(self) -> None:
        # This method is required by BaseBackend, but connection is managed internally
        # by the connection_manager. We can simply call its internal ensure_connected.
        self.connection_manager._ensure_connected()

    def initialize_audit_log_schema(self) -> None:
        self.audit_log_manager.initialize_audit_log_schema()

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        self.audit_log_manager.log_audit_event(entry)

    def log_quota_rejection(self, session: str, rejection_message: str, created_at: Optional[datetime] = None) -> None:
        conn = self.connection_manager.get_connection()
        ts = created_at if created_at is not None else datetime.now()
        self.quota_rejection_manager.log_rejection(conn, session, rejection_message, ts)
        conn.commit()

    def get_audit_log_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        app_name: Optional[str] = None,
        user_name: Optional[str] = None,
        project: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: Optional[int] = None,
        filter_project_null: Optional[bool] = None,
    ) -> List[AuditLogEntry]:
        return self.audit_log_manager.get_audit_log_entries(
            start_date, end_date, app_name, user_name, project, log_type, limit, filter_project_null
        )

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        """Retrieve aggregated usage costs for a user."""
        conn = self.connection_manager.get_connection()
        return self.usage_manager.get_usage_costs(conn, user_id, start_date, end_date)

    # --- Project management ---

    def create_project(self, name: str) -> None:
        self.project_manager.create_project(name)

    def list_projects(self) -> List[str]:
        return self.project_manager.list_projects()

    def update_project(self, name: str, new_name: str) -> None:
        self.project_manager.update_project(name, new_name)

    def delete_project(self, name: str) -> None:
        self.project_manager.delete_project(name)

    # --- User management ---

    def create_user(self, user_name: str, ou_name: Optional[str] = None, email: Optional[str] = None) -> None:
        self.user_manager.create_user(user_name, ou_name, email)

    def list_users(self) -> List[UserRecord]:
        records = self.user_manager.list_users()
        return [UserRecord(**r) for r in records]

    def update_user(
        self,
        user_name: str,
        new_user_name: Optional[str] = None,
        ou_name: Optional[str] = None,
        email: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.user_manager.update_user(user_name, new_user_name, ou_name, email, enabled)

    def set_user_enabled(self, user_name: str, enabled: bool) -> None:
        self.user_manager.set_user_enabled(user_name, enabled)
