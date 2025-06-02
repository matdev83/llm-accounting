import logging
import sqlite3 # Keep for type hints if sqlite_queries still use it, but primary connection is SQLAlchemy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session # Added for ORM-based insert
from llm_accounting.models.base import Base
from ..models.limits import LimitScope, LimitType, UsageLimitDTO, UsageLimit # Added UsageLimit model
from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry
from .sqlite_queries import (get_model_rankings_query, get_model_stats_query,
                             get_period_stats_query, insert_usage_query,
                             tail_query)
from .sqlite_utils import validate_db_filename
from ..db_migrations import run_migrations # Import run_migrations

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
        if not self.db_path.startswith("file:") and self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = None
        self.conn = None # SQLAlchemy connection

    def initialize(self) -> None:
        logger.info(f"Initializing SQLite backend for db: {self.db_path}")
        is_new_db = True
        db_connection_str = ""
        if self.db_path == ":memory:":
            logger.info("Using in-memory SQLite database.")
            db_connection_str = "sqlite:///:memory:"
        elif str(self.db_path).startswith("file:"):
            db_connection_str = f"sqlite:///{self.db_path}" # SQLAlchemy uses sqlite:/// for file URIs
            path_part = self.db_path.split('?')[0]
            if path_part.startswith("file:"):
                path_part = path_part[len("file:"):]
                # Remove extra slashes if present for local file paths
                if path_part.startswith('///'):
                    path_part = path_part[2:] 
                elif path_part.startswith('/'):
                     path_part = path_part[0:] # Keep one slash for absolute path
            # Ensure path_part is treated as a path for exists check
            if Path(path_part).exists() and Path(path_part).stat().st_size > 0:
                is_new_db = False
        else: # Standard file path
            db_path_obj = Path(self.db_path)
            if db_path_obj.exists() and db_path_obj.stat().st_size > 0:
                is_new_db = False
            db_connection_str = f"sqlite:///{self.db_path}"

        if self.engine is None:
            logger.info(f"Creating SQLAlchemy engine for {db_connection_str}")
            self.engine = create_engine(db_connection_str, future=True)
        
        if self.conn is None or self.conn.closed: # Ensure conn is open
            self.conn = self.engine.connect()

        # Run migrations for the SQLite database
        assert db_connection_str is not None, "DB connection string must be set before running migrations."
        run_migrations(db_url=db_connection_str)

        # Ensure schema is created via SQLAlchemy models if tables are missing.
        # This handles initial setup for new databases.
        if is_new_db:
            logger.info(f"Database {self.db_path} appears new. Creating schema.")
            Base.metadata.create_all(self.engine)
            logger.info("Schema creation complete.")
        else:
            logger.info(f"Database {self.db_path} exists. Skipping schema creation.")

    def insert_usage(self, entry: UsageEntry) -> None:
        """Insert a new usage entry into the database"""
        self._ensure_connected()
        assert self.conn is not None
        # Assuming insert_usage_query is adapted for SQLAlchemy connection and does not commit
        insert_usage_query(self.conn, entry)
        self.conn.commit()

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        self._ensure_connected()
        assert self.conn is not None
        # Assuming get_period_stats_query is adapted for SQLAlchemy connection
        return get_period_stats_query(self.conn, start, end)

    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        """Get statistics grouped by model for a time period"""
        self._ensure_connected()
        assert self.conn is not None
        # Assuming get_model_stats_query is adapted for SQLAlchemy connection
        return get_model_stats_query(self.conn, start, end)

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        self._ensure_connected()
        assert self.conn is not None
        # Assuming get_model_rankings_query is adapted for SQLAlchemy connection
        return get_model_rankings_query(self.conn, start, end)

    def purge(self) -> None:
        """Delete all usage entries from the database"""
        self._ensure_connected()
        assert self.conn is not None
        # Using text() for raw SQL with SQLAlchemy connection
        self.conn.execute(text("DELETE FROM accounting_entries"))
        self.conn.execute(text("DELETE FROM usage_limits"))
        self.conn.execute(text("DELETE FROM audit_log_entries")) # Added audit log table
        self.conn.commit()

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """Insert a new usage limit entry into the database."""
        self._ensure_connected()
        assert self.engine is not None # ORM operations typically use the engine/session

        db_limit = UsageLimit(
            scope=limit.scope,
            limit_type=limit.limit_type,
            max_value=limit.max_value,
            interval_unit=limit.interval_unit,
            interval_value=limit.interval_value,
            model=limit.model,
            username=limit.username,
            caller_name=limit.caller_name,
            project_name=limit.project_name
            # id, created_at, and updated_at are intentionally omitted
            # so that SQLAlchemy and the database can use their defaults.
        )
        
        # created_at and updated_at are managed by SQLAlchemy defaults and onupdate
        # No need to set them manually from DTO here.

        with Session(self.engine) as session:
            session.add(db_limit)
            session.commit()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        self._ensure_connected()
        assert self.conn is not None
        # Assuming tail_query is adapted for SQLAlchemy connection
        return tail_query(self.conn, n)

    def close(self) -> None:
        """Close the SQLAlchemy database connection"""
        if self.conn and not self.conn.closed:
            logger.info(f"Closing SQLAlchemy connection for {self.db_path}")
            self.conn.close()
        # Optional: Dispose engine if backend itself is being destroyed
        # if self.engine:
        #     logger.info(f"Disposing SQLAlchemy engine for {self.db_path}")
        #     self.engine.dispose()
        #     self.engine = None

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
            result = self.conn.execute(text(query))
            results = [dict(row._mapping) for row in result.fetchall()]
            return results
        except Exception as e: # Catch SQLAlchemy errors
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
        # Using text() for raw SQL with SQLAlchemy connection
        # Parameters will be bound automatically by SQLAlchemy
        query_base = "SELECT id, scope, limit_type, model, username, caller_name, project_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits WHERE 1=1"
        conditions = []
        params_dict: Dict[str, Any] = {}

        if scope:
            conditions.append("scope = :scope")
            params_dict["scope"] = scope.value
        if model:
            conditions.append("model = :model")
            params_dict["model"] = model
        
        if username is not None:
            conditions.append("username = :username")
            params_dict["username"] = username
        elif filter_username_null is True:
            conditions.append("username IS NULL")
        elif filter_username_null is False:
            conditions.append("username IS NOT NULL")

        if caller_name is not None:
            conditions.append("caller_name = :caller_name")
            params_dict["caller_name"] = caller_name
        elif filter_caller_name_null is True:
            conditions.append("caller_name IS NULL")
        elif filter_caller_name_null is False:
            conditions.append("caller_name IS NOT NULL")

        if project_name is not None:
            conditions.append("project_name = :project_name")
            params_dict["project_name"] = project_name
        elif filter_project_null is True:
            conditions.append("project_name IS NULL")
        elif filter_project_null is False:
            conditions.append("project_name IS NOT NULL")

        if conditions:
            query_base += " AND " + " AND ".join(conditions)
        
        result = self.conn.execute(text(query_base), params_dict)
        limits = []
        for row in result.fetchall():
            # Access by column name using row._mapping for SQLAlchemy Core
            row_map = row._mapping
            limits.append(
                UsageLimitDTO(
                    id=row_map["id"],
                    scope=row_map["scope"],
                    limit_type=row_map["limit_type"],
                    model=str(row_map["model"]) if row_map["model"] is not None else None,
                    username=str(row_map["username"]) if row_map["username"] is not None else None,
                    caller_name=str(row_map["caller_name"]) if row_map["caller_name"] is not None else None,
                    project_name=str(row_map["project_name"]) if row_map["project_name"] is not None else None,
                    max_value=row_map["max_value"],
                    interval_unit=row_map["interval_unit"],
                    interval_value=row_map["interval_value"],
                    created_at=(datetime.fromisoformat(row_map["created_at"]).replace(tzinfo=timezone.utc) if row_map["created_at"] else None),
                    updated_at=(datetime.fromisoformat(row_map["updated_at"]).replace(tzinfo=timezone.utc) if row_map["updated_at"] else None),
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

        # Using text() for raw SQL with SQLAlchemy connection
        # Parameters will be bound automatically by SQLAlchemy
        query_base = f"SELECT {select_clause} FROM accounting_entries WHERE timestamp >= :start_time"
        params_dict: Dict[str, Any] = {"start_time": start_time.isoformat()}
        conditions = []

        if model:
            conditions.append("model = :model")
            params_dict["model"] = model
        if username:
            conditions.append("username = :username")
            params_dict["username"] = username
        if caller_name:
            conditions.append("caller_name = :caller_name")
            params_dict["caller_name"] = caller_name
        
        if project_name is not None:
            conditions.append("project = :project_name") # Assuming 'project' is the column name in accounting_entries
            params_dict["project_name"] = project_name
        elif filter_project_null is True: # Corrected from if to elif
            conditions.append("project IS NULL")
        elif filter_project_null is False:
            conditions.append("project IS NOT NULL")

        if conditions:
            query_base += " AND " + " AND ".join(conditions)
        
        result = self.conn.execute(text(query_base), params_dict)
        scalar_result = result.scalar_one_or_none()
        return float(scalar_result) if scalar_result is not None else 0.0

    def delete_usage_limit(self, limit_id: int) -> None:
        """Delete a usage limit entry by its ID."""
        self._ensure_connected()
        assert self.conn is not None
        self.conn.execute(text("DELETE FROM usage_limits WHERE id = :limit_id"), {"limit_id": limit_id})
        self.conn.commit()

    def _ensure_connected(self) -> None:
        if self.engine is None: # Engine not created implies full init needed
            self.initialize()
        elif self.conn is None or self.conn.closed: # Engine exists, just (re)connect
            assert self.engine is not None # Should be true if this branch is hit
            self.conn = self.engine.connect()
        # If self.initialize() was called, it already establishes self.conn

    def initialize_audit_log_schema(self) -> None:
        """Ensure the audit log schema (e.g., tables) is initialized."""
        # This method is now largely a no-op or can be removed if initialize() handles all schema.
        # SQLAlchemy's Base.metadata.create_all(self.engine) in initialize() handles all tables.
        self._ensure_connected() 
        logger.info("Audit log schema is initialized as part of the main database initialization.")


    def log_audit_event(self, entry: AuditLogEntry) -> None:
        """Insert a new audit log entry."""
        self._ensure_connected()
        assert self.conn is not None

        query = """
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, prompt_text,
                response_text, remote_completion_id, project, log_type
            ) VALUES (:timestamp, :app_name, :user_name, :model, :prompt_text, :response_text, :remote_completion_id, :project, :log_type)
        """
        params = {
            "timestamp": entry.timestamp.isoformat(),
            "app_name": entry.app_name,
            "user_name": entry.user_name,
            "model": entry.model,
            "prompt_text": entry.prompt_text,
            "response_text": entry.response_text,
            "remote_completion_id": entry.remote_completion_id,
            "project": entry.project,
            "log_type": entry.log_type,
        }
        try:
            self.conn.execute(text(query), params)
            self.conn.commit()
        except Exception as e: # Catch SQLAlchemy errors
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

        # Using text() for raw SQL with SQLAlchemy connection
        # Parameters will be bound automatically by SQLAlchemy
        query_base = "SELECT id, timestamp, app_name, user_name, model, prompt_text, response_text, remote_completion_id, project, log_type FROM audit_log_entries"
        conditions = []
        params_dict: Dict[str, Any] = {}

        if start_date:
            conditions.append("timestamp >= :start_date")
            params_dict["start_date"] = start_date.isoformat()
        if end_date:
            conditions.append("timestamp <= :end_date")
            params_dict["end_date"] = end_date.isoformat()
        if app_name:
            conditions.append("app_name = :app_name")
            params_dict["app_name"] = app_name
        if user_name:
            conditions.append("user_name = :user_name")
            params_dict["user_name"] = user_name
        
        if project is not None:
            conditions.append("project = :project")
            params_dict["project"] = project
        elif filter_project_null is True:
            conditions.append("project IS NULL")
        elif filter_project_null is False:
            conditions.append("project IS NOT NULL")

        if log_type:
            conditions.append("log_type = :log_type")
            params_dict["log_type"] = log_type

        if conditions:
            query_base += " WHERE " + " AND ".join(conditions)

        query_base += " ORDER BY timestamp DESC"

        if limit is not None:
            query_base += " LIMIT :limit"
            params_dict["limit"] = limit
        
        results = []
        try:
            result_proxy = self.conn.execute(text(query_base), params_dict)
            for row in result_proxy.fetchall():
                # Access by column name using row._mapping for SQLAlchemy Core
                row_map = row._mapping
                results.append(
                    AuditLogEntry(
                        id=row_map["id"],
                        timestamp=datetime.fromisoformat(row_map["timestamp"]).replace(tzinfo=timezone.utc),
                        app_name=row_map["app_name"],
                        user_name=row_map["user_name"],
                        model=row_map["model"],
                        prompt_text=row_map["prompt_text"],
                        response_text=row_map["response_text"],
                        remote_completion_id=row_map["remote_completion_id"],
                        project=row_map["project"],
                        log_type=row_map["log_type"],
                    )
                )
        except Exception as e: # Catch SQLAlchemy errors
            logger.error(f"Failed to get audit log entries: {e}")
            # Depending on policy, might re-raise or handle
            raise
            
        return results

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        """Retrieve aggregated usage costs for a user."""
        self._ensure_connected()
        assert self.conn is not None

        query_base = "SELECT SUM(cost) FROM accounting_entries WHERE username = :user_id"
        params_dict: Dict[str, Any] = {"user_id": user_id}
        conditions = []

        if start_date:
            conditions.append("timestamp >= :start_date")
            params_dict["start_date"] = start_date.isoformat()
        if end_date:
            conditions.append("timestamp <= :end_date")
            params_dict["end_date"] = end_date.isoformat()

        if conditions:
            query_base += " AND " + " AND ".join(conditions)
        
        result = self.conn.execute(text(query_base), params_dict)
        scalar_result = result.scalar_one_or_none()
        return float(scalar_result) if scalar_result is not None else 0.0
