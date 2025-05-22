import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from llm_accounting.models.limits import UsageLimit
from llm_accounting.models.request import APIRequest

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
        assert self.conn is not None
        insert_usage_query(self.conn, entry)

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        assert self.conn is not None
        return get_period_stats_query(self.conn, start, end)

    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        """Get statistics grouped by model for a time period"""
        assert self.conn is not None
        return get_model_stats_query(self.conn, start, end)

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        assert self.conn is not None
        return get_model_rankings_query(self.conn, start, end)

    def purge(self) -> None:
        """Delete all usage entries from the database"""
        assert self.conn is not None
        self.conn.execute("DELETE FROM accounting_entries")
        self.conn.commit()

    def insert_usage_limit(self, limit: UsageLimit) -> None:
        """Insert a new usage limit entry into the database."""
        assert self.conn is not None
        self.conn.execute(
            """
            INSERT INTO usage_limits (scope, limit_type, max_value, interval_unit, interval_value, model, username, caller_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                limit.created_at.isoformat(),
                limit.updated_at.isoformat(),
            ),
        )
        self.conn.commit()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
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

        if not self.conn:
            self.initialize()

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

    def insert_api_request(self, request: APIRequest) -> None:
        """Insert a new API request entry into the database"""
        assert self.conn is not None
        self.conn.execute(
            """
            INSERT INTO api_requests (model, username, caller_name, input_tokens, output_tokens, cost, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.model,
                request.username,
                request.caller_name,
                request.input_tokens,
                request.output_tokens,
                request.cost,
                request.timestamp.isoformat(),
            ),
        )
        self.conn.commit()

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> List[UsageLimit]:
        assert self.conn is not None
        query = "SELECT id, scope, limit_type, model, username, caller_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits WHERE 1=1"
        params = []

        if scope:
            query += " AND scope = ?"
            params.append(scope.value)
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
        limits = []
        for row in cursor.fetchall():
            limits.append(
                UsageLimit(
                    id=row[0],
                    scope=row[1],
                    limit_type=row[2],
                    model=str(row[3]) if row[3] is not None else None,
                    username=str(row[4]) if row[4] is not None else None,
                    caller_name=str(row[5]) if row[5] is not None else None,
                    max_value=row[6],
                    interval_unit=row[7],
                    interval_value=row[8],
                    created_at=datetime.fromisoformat(row[9]) if row[9] else None,
                    updated_at=datetime.fromisoformat(row[10]) if row[10] else None,
                )
            )
        return limits

    def get_api_requests_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> float:
        assert self.conn is not None

        if limit_type == LimitType.REQUESTS:
            select_clause = "COUNT(*)"
        elif limit_type == LimitType.INPUT_TOKENS:
            select_clause = "SUM(input_tokens)"
        elif limit_type == LimitType.OUTPUT_TOKENS:
            select_clause = "SUM(output_tokens)"
        elif limit_type == LimitType.COST:
            select_clause = "SUM(cost)"
        else:
            raise ValueError(f"Unknown limit type: {limit_type}")

        query = f"SELECT {select_clause} FROM api_requests WHERE timestamp >= ?"
        params = [start_time.isoformat()]

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
        assert self.conn is not None
        self.conn.execute("DELETE FROM usage_limits WHERE id = ?", (limit_id,))
        self.conn.commit()
