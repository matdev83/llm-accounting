import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from llm_accounting.models.limits import UsageLimit, LimitScope, LimitType # Added LimitScope, LimitType
from .base import BaseBackend, UsageEntry, UsageStats # Removed LimitScope, LimitType from here if they were
from .sqlite_queries import (get_model_rankings_query, get_model_stats_query,
                             get_period_stats_query, insert_usage_query,
                             tail_query)
from .sqlite_utils import initialize_db_schema, validate_db_filename

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/accounting.sqlite"


class SQLiteBackend(BaseBackend):
    """SQLite implementation of the usage tracking backend"""

    def __init__(self, db_path: Optional[str] = None):
        actual_db_path = db_path if db_path is not None else DEFAULT_DB_PATH
        validate_db_filename(actual_db_path)
        self.db_path = actual_db_path
        if not self.db_path.startswith("file:"):
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Initialize the SQLite database"""
        # print(f"Initializing database at {self.db_path}") # Removed print
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
        self.conn.execute("DELETE FROM usage_limits") # Also purge usage_limits
        self.conn.commit()

    def insert_usage_limit(self, limit: UsageLimit) -> None:
        """Insert a new usage limit entry into the database."""
        self._ensure_connected()
        assert self.conn is not None
        self.conn.execute(
            """
            INSERT INTO usage_limits (
                scope, limit_type, max_value, interval_unit, interval_value, 
                model, username, caller_name, project_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                limit.scope,
                limit.limit_type,
                limit.max_value,
                limit.interval_unit,
                limit.interval_value,
                limit.model,
                limit.username,
                limit.caller_name,
                limit.project_name, # Added project_name
                limit.created_at.isoformat(),
                limit.updated_at.isoformat(),
            ),
        )
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
        """Execute a raw SQL SELECT query and return results."""
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
        project_name: Optional[str] = None, # Added project_name parameter
    ) -> List[UsageLimit]:
        self._ensure_connected()
        assert self.conn is not None
        # Added project_name to SELECT
        query = "SELECT id, scope, limit_type, model, username, caller_name, project_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits WHERE 1=1"
        params = []

        if scope:
            query += " AND scope = ?"
            params.append(scope.value) # Use enum value
        if model:
            query += " AND model = ?"
            params.append(model)
        if username:
            query += " AND username = ?"
            params.append(username)
        if caller_name:
            query += " AND caller_name = ?"
            params.append(caller_name)
        if project_name: # Filter by project_name
            query += " AND project_name = ?"
            params.append(project_name)
        
        # Special case for PROJECT scope if project_name is None (match limits where project_name IS NULL)
        # This is typically not how PROJECT scope limits would be defined (they should have a project_name),
        # but handling for completeness or specific use cases if a PROJECT scope limit can exist without a name.
        # However, usually, if scope is PROJECT, project_name will be provided.
        # If project_name is explicitly 'NULL_PROJECT_SENTINEL' or similar, then filter for IS NULL.
        # For now, direct match or IS NULL if project_name is None and scope is PROJECT.
        # This logic might be better placed in QuotaService or require a sentinel.
        # For simplicity here, if project_name is provided, it's an exact match.
        # If scope is PROJECT and project_name is None, it might imply a general project limit (not typical).

        cursor = self.conn.execute(query, params)
        limits = []
        for row in cursor.fetchall():
            limits.append(
                UsageLimit(
                    id=row[0],
                    scope=row[1], # Already string from DB, will be handled by UsageLimit constructor
                    limit_type=row[2], # Already string
                    model=str(row[3]) if row[3] is not None else None,
                    username=str(row[4]) if row[4] is not None else None,
                    caller_name=str(row[5]) if row[5] is not None else None,
                    project_name=str(row[6]) if row[6] is not None else None, # Added project_name
                    max_value=row[7],
                    interval_unit=row[8], # Already string
                    interval_value=row[9],
                    created_at=datetime.fromisoformat(row[10]) if row[10] else None,
                    updated_at=datetime.fromisoformat(row[11]) if row[11] else None,
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
        project_name: Optional[str] = None, # Added project_name
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
        params: List[Any] = [start_time.isoformat()] # Ensure params is explicitly typed

        if model:
            query += " AND model = ?"
            params.append(model)
        if username:
            query += " AND username = ?"
            params.append(username)
        if caller_name:
            query += " AND caller_name = ?"
            params.append(caller_name)
        if project_name: # Filter by project_name if provided
            query += " AND project = ?" # Assumes 'project' column in accounting_entries
            params.append(project_name)
        elif project_name is None: # Explicitly check for NULL if project_name is None for this query context
             # This part depends on desired behavior:
             # If project_name=None means "don't filter by project", then no clause is added.
             # If project_name=None means "filter for entries where project IS NULL", then add:
             # query += " AND project IS NULL"
             # For QuotaService, usually it's "don't filter unless specified".
             # However, if a PROJECT scope limit is being checked, and the incoming request has no project,
             # then we might want to sum usage for entries with NO project.
             # This logic is nuanced and depends on how _evaluate_limits decides to call this.
             # For now, if project_name is provided, filter by it. If None, no project filter.
             pass


        cursor = self.conn.execute(query, params)
        result = cursor.fetchone()
        # Ensure result and result[0] are not None before float conversion
        return float(result[0]) if result and result[0] is not None else 0.0


    def delete_usage_limit(self, limit_id: int) -> None:
        """Delete a usage limit entry by its ID."""
        self._ensure_connected()
        assert self.conn is not None
        self.conn.execute("DELETE FROM usage_limits WHERE id = ?", (limit_id,))
        self.conn.commit()

    def _ensure_connected(self) -> None:
        """Ensures the SQLite backend has an active connection."""
        if self.conn is None:
            self.initialize()
