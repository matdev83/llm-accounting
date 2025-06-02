import json 
import logging 
import sqlite3 
from datetime import datetime, timezone 
from pathlib import Path 
from typing import Dict, List, Optional, Tuple, Any 

import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import create_engine, text, func, desc, asc, and_, or_, extract
from sqlalchemy.orm import Session
from llm_accounting.models.base import Base
# Assuming AccountingEntry and AuditLogEntryModel are defined in models.accounting and models.audit respectively
from llm_accounting.models.accounting import AccountingEntry as AccountingEntryModel
from llm_accounting.models.audit import AuditLogEntryModel
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

    def get_usage_limits_ui(
        self,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        self._ensure_connected()
        assert self.engine is not None
        with Session(self.engine) as session:
            query = session.query(UsageLimit)

            if filters:
                filter_clauses = []
                for key, value in filters.items():
                    if value is None or str(value).strip() == "":
                        continue
                    column = getattr(UsageLimit, key, None)
                    if column:
                        if isinstance(value, str) and hasattr(column.comparator, 'ilike'):
                            filter_clauses.append(column.ilike(f"%{value}%"))
                        else:
                            filter_clauses.append(column == value)
                if filter_clauses:
                    query = query.filter(and_(*filter_clauses))
            
            results = query.order_by(desc(UsageLimit.created_at)).all()
            return [self._row_to_dict(row, UsageLimit) for row in results]

    def get_accounting_entries(
        self,
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        filters: Optional[dict] = None,
    ) -> Tuple[List[dict], int]:
        self._ensure_connected()
        assert self.engine is not None
        with Session(self.engine) as session:
            query = session.query(AccountingEntryModel)
            
            if filters:
                query = self._apply_filters(query, AccountingEntryModel, filters)

            total_count = query.count()

            if sort_by:
                column = getattr(AccountingEntryModel, sort_by, None)
                if column:
                    if sort_order.lower() == "desc":
                        query = query.order_by(desc(column))
                    else:
                        query = query.order_by(asc(column))
            
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            results = query.all()
            # Convert to dicts
            return [self._row_to_dict(row, AccountingEntryModel) for row in results], total_count

    def _row_to_dict(self, row, model_cls):
        """Helper to convert SQLAlchemy model instance to dict."""
        d = {}
        for column in model_cls.__table__.columns:
            val = getattr(row, column.name)
            if isinstance(val, datetime):
                d[column.name] = val.isoformat()
            else:
                d[column.name] = val
        return d

    def _apply_filters(self, query, model_cls, filters: dict):
        filter_clauses = []
        for key, value in filters.items():
            if value is None or str(value).strip() == "":
                continue
            
            column = getattr(model_cls, key, None)
            if column:
                if key == "timestamp_start":
                    filter_clauses.append(column >= value)
                elif key == "timestamp_end":
                    # Add 1 day to make it inclusive if it's just a date
                    if isinstance(value, datetime) and value.hour == 0 and value.minute == 0 and value.second == 0:
                         value = value + timedelta(days=1)
                    filter_clauses.append(column < value)
                elif isinstance(value, str) and hasattr(column.comparator, 'ilike'):
                     filter_clauses.append(column.ilike(f"%{value}%"))
                else:
                    filter_clauses.append(column == value)
            elif key == "search_term" and isinstance(value, str):
                search_clauses = []
                # Define columns to search for the given model_cls
                if model_cls == AccountingEntryModel:
                    searchable_cols = ["model", "project", "caller_name", "username"]
                elif model_cls == AuditLogEntryModel:
                    searchable_cols = ["app_name", "user_name", "model", "project", "log_type", "prompt_text", "response_text"]
                else:
                    searchable_cols = []

                for col_name in searchable_cols:
                    col = getattr(model_cls, col_name, None)
                    if col and hasattr(col.comparator, 'ilike'):
                        search_clauses.append(col.ilike(f"%{value}%"))
                if search_clauses:
                    filter_clauses.append(or_(*search_clauses))
        
        if filter_clauses:
            query = query.filter(and_(*filter_clauses))
        return query

    def get_custom_stats(
        self,
        group_by: List[str],
        aggregates: List[str],
        time_horizon: str,
        time_filters: Optional[dict] = None,
        additional_filters: Optional[dict] = None,
    ) -> List[dict]:
        self._ensure_connected()
        assert self.engine is not None

        with Session(self.engine) as session:
            selection_columns = []
            group_by_columns = []

            # Handle time grouping
            time_group_col_name = None
            if time_horizon == 'daily':
                selection_columns.append(func.strftime('%Y-%m-%d', AccountingEntryModel.timestamp).label('time_group'))
                group_by_columns.append(func.strftime('%Y-%m-%d', AccountingEntryModel.timestamp))
                time_group_col_name = 'time_group'
            elif time_horizon == 'weekly':
                # SQLite: %W means week of year (Sunday as first day of week)
                # To make it more like ISO week, we can use %Y-%W or combine with year
                selection_columns.append(func.strftime('%Y-%W', AccountingEntryModel.timestamp).label('time_group'))
                group_by_columns.append(func.strftime('%Y-%W', AccountingEntryModel.timestamp))
                time_group_col_name = 'time_group'
            elif time_horizon == 'monthly':
                selection_columns.append(func.strftime('%Y-%m', AccountingEntryModel.timestamp).label('time_group'))
                group_by_columns.append(func.strftime('%Y-%m', AccountingEntryModel.timestamp))
                time_group_col_name = 'time_group'
            
            # Handle other group_by columns
            for col_name in group_by:
                if hasattr(AccountingEntryModel, col_name):
                    selection_columns.append(getattr(AccountingEntryModel, col_name))
                    group_by_columns.append(getattr(AccountingEntryModel, col_name))

            # Handle aggregations
            agg_map = {
                'sum_prompt_tokens': func.sum(AccountingEntryModel.prompt_tokens),
                'sum_completion_tokens': func.sum(AccountingEntryModel.completion_tokens),
                'sum_total_tokens': func.sum(AccountingEntryModel.total_tokens),
                'sum_cost': func.sum(AccountingEntryModel.cost),
                'sum_execution_time': func.sum(AccountingEntryModel.execution_time),
                'avg_prompt_tokens': func.avg(AccountingEntryModel.prompt_tokens),
                'avg_completion_tokens': func.avg(AccountingEntryModel.completion_tokens),
                'avg_total_tokens': func.avg(AccountingEntryModel.total_tokens),
                'avg_cost': func.avg(AccountingEntryModel.cost),
                'avg_execution_time': func.avg(AccountingEntryModel.execution_time),
                'count_entries': func.count(AccountingEntryModel.id),
            }
            for agg_name in aggregates:
                if agg_name in agg_map:
                    selection_columns.append(agg_map[agg_name].label(agg_name))
                else:
                    logger.warning(f"Unsupported aggregate: {agg_name}")

            if not selection_columns:
                return [] # No valid columns to select or aggregate

            query = session.query(*selection_columns)

            # Apply time_filters
            if time_filters:
                if time_horizon == 'custom': # Only apply if horizon is custom, otherwise it's part of grouping
                    if 'timestamp_start' in time_filters:
                        query = query.filter(AccountingEntryModel.timestamp >= time_filters['timestamp_start'])
                    if 'timestamp_end' in time_filters:
                        end_date = time_filters['timestamp_end']
                        if isinstance(end_date, datetime) and end_date.hour == 0 and end_date.minute == 0 and end_date.second == 0:
                            end_date = end_date + timedelta(days=1) # Make it exclusive for end of day
                        query = query.filter(AccountingEntryModel.timestamp < end_date)
            
            # Apply additional_filters
            if additional_filters:
                query = self._apply_filters(query, AccountingEntryModel, additional_filters)

            # Apply group_by
            if group_by_columns:
                query = query.group_by(*group_by_columns)
            
            # Order by time_group if it exists, then by other group_by columns
            if time_group_col_name:
                 query = query.order_by(desc(time_group_col_name)) # Typically want recent time groups first
            for col_name in group_by:
                 if hasattr(AccountingEntryModel, col_name):
                      query = query.order_by(getattr(AccountingEntryModel, col_name))


            results = query.all()
            
            # Convert RowProxy to dict
            # The column names are available from the result keys
            if results and hasattr(results[0], '_fields'):
                keys = results[0]._fields
                return [dict(zip(keys, row)) for row in results]
            return []


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
        assert self.engine is not None
        with Session(self.engine) as session:
            query = session.query(AuditLogEntryModel)

            if filters:
                query = self._apply_filters(query, AuditLogEntryModel, filters)

            total_count = query.count()

            if sort_by:
                column = getattr(AuditLogEntryModel, sort_by, None)
                if column:
                    if sort_order.lower() == "desc":
                        query = query.order_by(desc(column))
                    else:
                        query = query.order_by(asc(column))
            else: # Default sort for audit logs
                query = query.order_by(desc(AuditLogEntryModel.timestamp))
            
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            results = query.all()
            return [self._row_to_dict(row, AuditLogEntryModel) for row in results], total_count

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
