import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ..models.limits import LimitScope, LimitType, UsageLimitDTO
from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry
from .sqlite_queries import (get_model_rankings_query, get_model_stats_query,
                             get_period_stats_query, insert_usage_query,
                             tail_query)
from .sqlite_utils import initialize_db_schema, validate_db_filename

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/accounting.sqlite"


class SQLiteBackend(BaseBackend):
    """SQLite implementation of the usage tracking backend

    This class provides a concrete implementation of the BaseBackend using SQLite
    for persistent storage of LLM usage tracking data. It handles database schema
    initialization, connection management, and implements all required operations
    for usage tracking including insertion, querying, and aggregation of usage data.

    Key Features:
    - Uses SQLite for persistent storage with configurable database path
    - Automatically creates database schema on initialization
    - Supports raw SQL query execution for advanced analytics
    - Implements usage limits and quota tracking capabilities
    - Handles connection lifecycle management
    """

    def __init__(self, db_path: Optional[str] = None):
        actual_db_path = db_path if db_path is not None else DEFAULT_DB_PATH
        validate_db_filename(actual_db_path)
        self.db_path = actual_db_path
        if not self.db_path.startswith("file:"):
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Initialize the SQLite database"""
        if str(self.db_path).startswith("file:"):
            self.conn = sqlite3.connect(self.db_path, uri=True)
        else:
            self.conn = sqlite3.connect(self.db_path)
        initialize_db_schema(self.conn)

    def insert_usage(self, entry: UsageEntry) -> None:
        """Insert a new usage entry into the database"""
        self._ensure_connected()
        assert self.conn is not None
        insert_usage_query(self.conn, entry)

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        self._ensure_connected()
        assert self.conn is not None
        return get_period_stats_query(self.conn, start, end)

    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        """Get statistics grouped by model for a time period"""
        self._ensure_connected()
        assert self.conn is not None
        return get_model_stats_query(self.conn, start, end)

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        self._ensure_connected()
        assert self.conn is not None
        return get_model_rankings_query(self.conn, start, end)

    def purge(self) -> None:
        """Delete all usage entries from the database"""
        self._ensure_connected()
        assert self.conn is not None
        self.conn.execute("DELETE FROM accounting_entries")
        self.conn.execute("DELETE FROM usage_limits")
        self.conn.commit()

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """Insert a new usage limit entry into the database."""
        self._ensure_connected()
        assert self.conn is not None

        columns = ["scope", "limit_type", "max_value", "interval_unit", "interval_value", "model", "username", "caller_name", "project_name"]
        params = [
            limit.scope,
            limit.limit_type,
            limit.max_value,
            limit.interval_unit,
            limit.interval_value,
            limit.model,
            limit.username,
            limit.caller_name,
            limit.project_name,
        ]

        if limit.created_at is not None:
            columns.append("created_at")
            params.append(limit.created_at.isoformat())

        if limit.updated_at is not None:
            columns.append("updated_at")
            params.append(limit.updated_at.isoformat())

        column_names = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(params))
        query = f"INSERT INTO usage_limits ({column_names}) VALUES ({placeholders})"

        self.conn.execute(query, tuple(params))
        self.conn.commit()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        self._ensure_connected()
        assert self.conn is not None
        return tail_query(self.conn, n)

    def close(self) -> None:
        """Close the database connection"""
        if self.conn:
            logger.info(f"Attempting to close sqlite connection for {self.db_path}")
            self.conn.close()
            logger.info(f"sqlite connection closed for {self.db_path}")
            self.conn = None
            logger.info(f"self.conn set to None for {self.db_path}")
        else:
            logger.info(f"No sqlite connection to close for {self.db_path}")

    def execute_query(self, query: str) -> List[Dict]:
        """
        Execute a raw SQL SELECT query and return results.
        If the connection is not already open, it will be initialized.
        It is recommended to use this method within the LLMAccounting context manager
        to ensure proper connection management (opening and closing).
        """
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed.")

        self._ensure_connected()

        assert self.conn is not None
        try:
            original_row_factory = self.conn.row_factory
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute(query)
            results = [dict(row) for row in cursor.fetchall()]
            self.conn.row_factory = original_row_factory
            return results
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error: {e}") from e

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
        self._ensure_connected()
        assert self.conn is not None
        query = "SELECT id, scope, limit_type, model, username, caller_name, project_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits WHERE 1=1"
        params = []

        if scope:
            query += " AND scope = ?"
            params.append(scope.value)
        if model:
            query += " AND model = ?"
            params.append(model)
        
        # Handle username filtering
        if username is not None:
            query += " AND username = ?"
            params.append(username)
        elif filter_username_null is True:
            query += " AND username IS NULL"
        elif filter_username_null is False:
            query += " AND username IS NOT NULL"

        # Handle caller_name filtering
        if caller_name is not None:
            query += " AND caller_name = ?"
            params.append(caller_name)
        elif filter_caller_name_null is True:
            query += " AND caller_name IS NULL"
        elif filter_caller_name_null is False:
            query += " AND caller_name IS NOT NULL"

        if project_name is not None:
            query += " AND project_name = ?"
            params.append(project_name)
        elif filter_project_null is True:
            query += " AND project_name IS NULL"
        elif filter_project_null is False:
            query += " AND project_name IS NOT NULL"


        cursor = self.conn.execute(query, params)
        limits = []
        for row in cursor.fetchall():
            limits.append(
                UsageLimitDTO(
                    id=row[0],
                    scope=row[1],
                    limit_type=row[2],
                    model=str(row[3]) if row[3] is not None else None,
                    username=str(row[4]) if row[4] is not None else None,
                    caller_name=str(row[5]) if row[5] is not None else None,
                    project_name=str(row[6]) if row[6] is not None else None,
                    max_value=row[7],
                    interval_unit=row[8],
                    interval_value=row[9],
                    created_at=(datetime.fromisoformat(row[10]).replace(tzinfo=timezone.utc) if row[10] else None),
                    updated_at=(datetime.fromisoformat(row[11]).replace(tzinfo=timezone.utc) if row[11] else None),
                )
            )
        return limits

    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None, # New parameter
    ) -> float:
        self._ensure_connected()
        assert self.conn is not None

        if limit_type == LimitType.REQUESTS:
            select_clause = "COUNT(*)"
        elif limit_type == LimitType.INPUT_TOKENS:
            select_clause = "SUM(prompt_tokens)"
        elif limit_type == LimitType.OUTPUT_TOKENS:
            select_clause = "SUM(completion_tokens)"
        elif limit_type == LimitType.COST:
            select_clause = "SUM(cost)"
        else:
            raise ValueError(f"Unknown limit type: {limit_type}")

        query = f"SELECT {select_clause} FROM accounting_entries WHERE timestamp >= ?"
        params: List[Any] = [start_time.isoformat()]

        if model:
            query += " AND model = ?"
            params.append(model)
        if username:
            query += " AND username = ?"
            params.append(username)
        if caller_name:
            query += " AND caller_name = ?"
            params.append(caller_name)
        
        if project_name is not None:
            query += " AND project = ?"
            params.append(project_name)
        if filter_project_null is True:
            query += " AND project IS NULL"
        if filter_project_null is False:
            query += " AND project IS NOT NULL"

        cursor = self.conn.execute(query, params)
        result = cursor.fetchone()
        return float(result[0]) if result and result[0] is not None else 0.0

    def delete_usage_limit(self, limit_id: int) -> None:
        """Delete a usage limit entry by its ID."""
        self._ensure_connected()
        assert self.conn is not None
        self.conn.execute("DELETE FROM usage_limits WHERE id = ?", (limit_id,))
        self.conn.commit()

    def _ensure_connected(self) -> None:
        """
        Ensures the SQLite backend has an active connection.
        Initializes the connection if it's None.
        """
        if self.conn is None:
            self.initialize()

    def initialize_audit_log_schema(self) -> None:
        """Ensure the audit log schema (e.g., tables) is initialized."""
        # The main initialize() method already creates all schemas including audit_log_entries
        # via initialize_db_schema.
        self._ensure_connected()
        # Optionally, explicitly call initialize_db_schema if it's idempotent and needed for clarity
        # initialize_db_schema(self.conn)

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        """Insert a new audit log entry."""
        self._ensure_connected()
        assert self.conn is not None

        query = """
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, prompt_text,
                response_text, remote_completion_id, project, log_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            entry.timestamp.isoformat(),
            entry.app_name,
            entry.user_name,
            entry.model,
            entry.prompt_text,
            entry.response_text,
            entry.remote_completion_id,
            entry.project,
            entry.log_type,
        )
        try:
            self.conn.execute(query, params)
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to log audit event: {e}")
            # Depending on policy, might re-raise or handle
            raise

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
        """Retrieve audit log entries based on filter criteria."""
        self._ensure_connected()
        assert self.conn is not None

        original_row_factory = self.conn.row_factory
        self.conn.row_factory = sqlite3.Row

        query_parts = ["SELECT id, timestamp, app_name, user_name, model, prompt_text, response_text, remote_completion_id, project, log_type FROM audit_log_entries"]
        conditions = []
        params: List[Any] = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date.isoformat())
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date.isoformat())
        if app_name:
            conditions.append("app_name = ?")
            params.append(app_name)
        if user_name:
            conditions.append("user_name = ?")
            params.append(user_name)
        
        # Handle project filtering
        if project is not None:
            conditions.append("project = ?")
            params.append(project)
        elif filter_project_null is True:
            conditions.append("project IS NULL")
        elif filter_project_null is False:
            conditions.append("project IS NOT NULL")

        if log_type:
            conditions.append("log_type = ?")
            params.append(log_type)

        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))

        query_parts.append("ORDER BY timestamp DESC")

        if limit is not None:
            query_parts.append("LIMIT ?")
            params.append(limit)

        final_query = " ".join(query_parts)
        
        results = []
        try:
            cursor = self.conn.execute(final_query, params)
            for row in cursor.fetchall():
                results.append(
                    AuditLogEntry(
                        id=row["id"],
                        timestamp=datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc),
                        app_name=row["app_name"],
                        user_name=row["user_name"],
                        model=row["model"],
                        prompt_text=row["prompt_text"],
                        response_text=row["response_text"],
                        remote_completion_id=row["remote_completion_id"],
                        project=row["project"],
                        log_type=row["log_type"],
                    )
                )
        except sqlite3.Error as e:
            logger.error(f"Failed to get audit log entries: {e}")
            # Depending on policy, might re-raise or handle
            raise
        finally:
            self.conn.row_factory = original_row_factory
            
        return results
