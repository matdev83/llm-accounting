import logging
import sqlite3
from datetime import datetime, timezone # Added timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Removed: from llm_accounting.models.limits import UsageLimit
# Added:
from ..models.limits import UsageLimitData
from .base import BaseBackend, LimitScope, LimitType, UsageEntry, UsageStats
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

    The backend is designed to be used within the LLMAccounting context manager
    to ensure proper connection handling and resource cleanup.
    """

    def __init__(self, db_path: Optional[str] = None):
        actual_db_path = db_path if db_path is not None else DEFAULT_DB_PATH
        validate_db_filename(actual_db_path)
        self.db_path = actual_db_path  # Store as string
        if not self.db_path.startswith("file:"):
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Initialize the SQLite database"""
        print(f"Initializing database at {self.db_path}")
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
        self.conn.execute("DELETE FROM usage_limits") # Added to also purge usage_limits
        self.conn.commit()

    def insert_usage_limit(self, limit_data: UsageLimitData) -> None: # Signature updated
        """Insert a new usage limit entry into the database."""
        self._ensure_connected()
        assert self.conn is not None

        columns = ["scope", "limit_type", "max_value", "interval_unit", "interval_value", "model", "username", "caller_name"]
        params = [
            limit_data.scope,
            limit_data.limit_type,
            limit_data.max_value,
            limit_data.interval_unit,
            limit_data.interval_value,
            limit_data.model,
            limit_data.username,
            limit_data.caller_name,
        ]

        if limit_data.created_at is not None:
            columns.append("created_at")
            params.append(limit_data.created_at.isoformat())

        if limit_data.updated_at is not None:
            columns.append("updated_at")
            params.append(limit_data.updated_at.isoformat())

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

        assert self.conn is not None  # For type checking
        try:
            # Set row_factory to sqlite3.Row to access columns by name
            original_row_factory = self.conn.row_factory
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute(query)
            results = [dict(row) for row in cursor.fetchall()]
            self.conn.row_factory = original_row_factory  # Restore original row_factory
            return results
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error: {e}") from e

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> List[UsageLimitData]: # Return type updated
        self._ensure_connected()
        assert self.conn is not None
        query = "SELECT id, scope, limit_type, model, username, caller_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits WHERE 1=1"
        params = []

        if scope:
            query += " AND scope = ?"
            params.append(scope.value) # scope is an enum, use .value
        if model:
            query += " AND model = ?"
            params.append(model)
        
        # Modified username handling for IS NULL vs specific value
        if username is not None:
            query += " AND username = ?"
            params.append(username)
        else:
            # If username is explicitly None in the filter, query for limits where username IS NULL
            # This is relevant for general CALLER or GLOBAL limits that are not user-specific.
            # However, get_usage_limits for GLOBAL/MODEL scopes typically don't pass username.
            # This 'else' branch is mainly for distinguishing general CALLER limits (username IS NULL)
            # from specific user-caller limits when scope=LimitScope.CALLER.
            if scope == LimitScope.CALLER or scope == LimitScope.GLOBAL: # Ensure this applies only where relevant
                 query += " AND username IS NULL"

        if caller_name:
            query += " AND caller_name = ?"
            params.append(caller_name)

        cursor = self.conn.execute(query, params)
        limits = []
        for row in cursor.fetchall():
            limits.append(
                UsageLimitData( # Instantiation updated
                    id=row[0],
                    scope=row[1],
                    limit_type=row[2],
                    model=str(row[3]) if row[3] is not None else None,
                    username=str(row[4]) if row[4] is not None else None,
                    caller_name=str(row[5]) if row[5] is not None else None,
                    max_value=row[6],
                    interval_unit=row[7],
                    interval_value=row[8],
                    # Ensure created_at and updated_at are timezone-aware (UTC) after parsing
                    created_at=(datetime.fromisoformat(row[9]).replace(tzinfo=timezone.utc) if row[9] else None),
                    updated_at=(datetime.fromisoformat(row[10]).replace(tzinfo=timezone.utc) if row[10] else None),
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
        # Convert datetime to string for query
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

        cursor = self.conn.execute(query, params)
        result = cursor.fetchone()[0]
        return float(result) if result is not None else 0.0

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
