import json 
import logging 
import sqlite3 
from datetime import datetime, timezone 
from pathlib import Path 
from typing import Dict, List, Optional, Tuple, Any 

from sqlalchemy import create_engine, text 
from sqlalchemy.orm import Session 
from llm_accounting.models.base import Base 
from ..models.limits import LimitScope, LimitType, UsageLimitDTO, UsageLimit 
from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry 
from .sqlite_queries import (get_model_rankings_query, get_model_stats_query, 
                             get_period_stats_query, insert_usage_query, 
                             tail_query) 
from .sqlite_utils import validate_db_filename 
# MODIFIED IMPORT BELOW
from ..db_migrations import run_migrations, get_head_revision, stamp_db_head

logger = logging.getLogger(__name__) 

DEFAULT_DB_PATH = "data/accounting.sqlite" 
MIGRATION_CACHE_PATH = "data/migration_status.json" # Used as Path(MIGRATION_CACHE_PATH)


class SQLiteBackend(BaseBackend): 
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
        
        # Determine db_connection_str and is_new_db status
        if self.db_path == ":memory:":
            logger.info("Using in-memory SQLite database.")
            db_connection_str = "sqlite:///:memory:"
            is_new_db = True # In-memory is always conceptually new in terms of persistence
        elif str(self.db_path).startswith("file:"):
            db_connection_str = f"sqlite:///{self.db_path}"
            path_part = self.db_path.split('?')[0]
            if path_part.startswith("file:"):
                path_part = path_part[len("file:"):]
                if path_part.startswith('///'):
                    path_part = path_part[2:]
                elif path_part.startswith('/'):
                    path_part = path_part[0:]
            if Path(path_part).exists() and Path(path_part).stat().st_size > 0:
                is_new_db = False
        else: 
            db_path_obj = Path(self.db_path)
            if db_path_obj.exists() and db_path_obj.stat().st_size > 0:
                is_new_db = False
            db_connection_str = f"sqlite:///{self.db_path}"

        # Setup SQLAlchemy engine and connection
        if self.engine is None:
            logger.info(f"Creating SQLAlchemy engine for {db_connection_str}")
            self.engine = create_engine(db_connection_str, future=True)
        if self.conn is None or self.conn.closed: 
            self.conn = self.engine.connect()

        migration_cache_file = Path(MIGRATION_CACHE_PATH) # Define for use in file ops

        # Main logic based on DB type and state
        if self.db_path == ":memory:":
            logger.info("Initializing in-memory SQLite database: running migrations and ensuring schema.")
            # For in-memory, we typically want the latest schema.
            # Running migrations ensures Alembic history is aligned if it were a persistent DB.
            # Then create_all ensures any non-Alembic managed tables (if any) are also present.
            run_migrations(db_url=db_connection_str) 
            Base.metadata.create_all(self.engine)
            logger.info("In-memory database initialization complete.")
            # No caching for in-memory databases
        
        elif is_new_db:
            logger.info(f"Database {self.db_path} is new. Creating schema from models and stamping with head revision.")
            Base.metadata.create_all(self.engine)
            logger.info("Schema creation complete for new database.")
            
            stamped_revision = stamp_db_head(db_connection_str)
            if stamped_revision:
                try:
                    migration_cache_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(migration_cache_file, "w") as f_cache: # Use migration_cache_file Path object
                        json.dump({"db_path": self.db_path, "revision": stamped_revision}, f_cache)
                    logger.info(f"Migration cache updated with stamped head revision: {stamped_revision}")
                except IOError as e:
                    logger.warning(f"Could not write migration cache file {migration_cache_file}: {e}")
            else:
                logger.warning(f"Could not determine revision after stamping new database {self.db_path}. Cache not updated.")
        
        else: # Existing disk-based database
            logger.info(f"Existing database {self.db_path} found. Checking migration status.")
            cached_revision: Optional[str] = None
            if migration_cache_file.exists():
                try:
                    with open(migration_cache_file, "r") as f:
                        cache_data = json.load(f)
                    if cache_data.get("db_path") == self.db_path:
                        cached_revision = cache_data.get("revision")
                        logger.info(f"Found cached migration revision: {cached_revision} for {self.db_path}")
                    else:
                        logger.warning(f"Cache file {migration_cache_file} db_path does not match current {self.db_path}. Ignoring cache.")
                except Exception as e:
                    logger.warning(f"Could not read migration cache file {migration_cache_file}: {e}")

            current_head_script_revision = get_head_revision(db_connection_str)
            logger.info(f"Determined current head script revision: {current_head_script_revision}")
            
            run_migrations_needed = False
            if cached_revision is None:
                logger.info(f"No valid cached revision found for {self.db_path}. Migrations will run.")
                run_migrations_needed = True
            elif current_head_script_revision is None:
                logger.warning(f"Could not determine head script revision for {self.db_path}. Migrations will run as a precaution.")
                run_migrations_needed = True
            elif cached_revision != current_head_script_revision:
                logger.info(f"Cached revision {cached_revision} differs from head script revision {current_head_script_revision} for {self.db_path}. Migrations will run.")
                run_migrations_needed = True
            else:
                logger.info(f"Cached revision {cached_revision} matches head script revision {current_head_script_revision}. Migrations will be skipped.")

            if run_migrations_needed:
                logger.info(f"Running migrations for existing database {self.db_path}...")
                db_rev_after_migration = run_migrations(db_url=db_connection_str)
                logger.info(f"Migrations completed for {self.db_path}. Reported database revision: {db_rev_after_migration}")

                if db_rev_after_migration:
                    try:
                        migration_cache_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(migration_cache_file, "w") as f_cache: # Use migration_cache_file Path object
                            json.dump({"db_path": self.db_path, "revision": db_rev_after_migration}, f_cache)
                        logger.info(f"Migration cache updated for {self.db_path} with revision {db_rev_after_migration}")
                    except IOError as e:
                        logger.warning(f"Could not write migration cache file {migration_cache_file}: {e}")
                else:
                    logger.warning(f"run_migrations did not return a revision for {self.db_path}. Cache not updated.")
            
            # For existing databases, schema is managed by migrations. Base.metadata.create_all() is not called.
            logger.info(f"Initialization for existing database {self.db_path} complete. Schema assumed to be managed by migrations.")


    def insert_usage(self, entry: UsageEntry) -> None:
        """Insert a new usage entry into the database"""
        self._ensure_connected()
        assert self.conn is not None
        insert_usage_query(self.conn, entry)
        self.conn.commit()

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
        self.conn.execute(text("DELETE FROM accounting_entries"))
        self.conn.execute(text("DELETE FROM usage_limits"))
        self.conn.execute(text("DELETE FROM audit_log_entries")) 
        self.conn.commit()

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """Insert a new usage limit entry into the database."""
        self._ensure_connected()
        assert self.engine is not None 

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
        )
        
        with Session(self.engine) as session:
            session.add(db_limit)
            session.commit()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        self._ensure_connected()
        assert self.conn is not None
        return tail_query(self.conn, n)

    def close(self) -> None:
        """Close the SQLAlchemy database connection"""
        if self.conn and not self.conn.closed:
            logger.info(f"Closing SQLAlchemy connection for {self.db_path}")
            self.conn.close()

    def execute_query(self, query: str) -> List[Dict]:
        """
        Execute a raw SQL SELECT query and return results.
        """
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed.")

        self._ensure_connected()
        assert self.conn is not None
        try:
            result = self.conn.execute(text(query))
            results = [dict(row._mapping) for row in result.fetchall()]
            return results
        except Exception as e: 
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
        filter_project_null: Optional[bool] = None, 
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
            conditions.append("project = :project_name") 
            params_dict["project_name"] = project_name
        elif filter_project_null is True: 
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
        if self.engine is None: 
            self.initialize()
        elif self.conn is None or self.conn.closed: 
            assert self.engine is not None 
            self.conn = self.engine.connect()

    def initialize_audit_log_schema(self) -> None:
        self._ensure_connected() 
        logger.info("Audit log schema is initialized as part of the main database initialization.")

    def log_audit_event(self, entry: AuditLogEntry) -> None:
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
        except Exception as e: 
            logger.error(f"Failed to log audit event: {e}")
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
        self._ensure_connected()
        assert self.conn is not None

        # Original query from file had "remote_completion_id"
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
        except Exception as e: 
            logger.error(f"Failed to get audit log entries: {e}")
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
