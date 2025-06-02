import logging
import os
import psycopg2
import psycopg2.extras  # For RealDictCursor
import psycopg2.extensions  # For connection type
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
import json # Added
from pathlib import Path # Added

from sqlalchemy import create_engine, text, inspect
from llm_accounting.models.base import Base

from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry
from ..models.limits import UsageLimitDTO, LimitScope, LimitType
# Updated import
from ..db_migrations import run_migrations, get_head_revision, stamp_db_head 

from .postgresql_backend_parts.connection_manager import ConnectionManager
from .postgresql_backend_parts.schema_manager import SchemaManager # Retained if used by other parts
from .postgresql_backend_parts.data_inserter import DataInserter
from .postgresql_backend_parts.data_deleter import DataDeleter
from .postgresql_backend_parts.query_executor import QueryExecutor
from .postgresql_backend_parts.limit_manager import LimitManager

logger = logging.getLogger(__name__)

POSTGRES_MIGRATION_CACHE_PATH = "data/postgres_migration_status.json" # Added

class PostgreSQLBackend(BaseBackend):
    conn: Optional[psycopg2.extensions.connection] = None
    """
    A backend for llm-accounting that uses a PostgreSQL database, specifically
    tailored for Neon serverless Postgres but compatible with standard PostgreSQL instances.
    """

    def __init__(self, postgresql_connection_string: Optional[str] = None):
        """
        Initializes the PostgreSQLBackend.
        """
        if postgresql_connection_string:
            self.connection_string = postgresql_connection_string
        else:
            self.connection_string = os.environ.get("POSTGRESQL_CONNECTION_STRING")

        if not self.connection_string:
            raise ValueError(
                "PostgreSQL connection string not provided and POSTGRESQL_CONNECTION_STRING "
                "environment variable is not set."
            )
        self.conn = None
        self.engine = None
        self.cached_postgres_revision: Optional[str] = None # Added
        logger.info("PostgreSQLBackend initialized with connection string.")

        self.connection_manager = ConnectionManager(self)
        # SchemaManager might be deprecated if all schema logic moves here
        self.schema_manager = SchemaManager(self) 
        self.data_inserter = DataInserter(self)
        self.data_deleter = DataDeleter(self)
        self.query_executor = QueryExecutor(self)
        self.limit_manager = LimitManager(self, self.data_inserter)

    def initialize(self) -> None:
        """
        Connects to the PostgreSQL database, sets up the SQLAlchemy engine,
        and manages schema creation/migration with caching.
        """
        # --- Cache Reading ---
        migration_cache_file = Path(POSTGRES_MIGRATION_CACHE_PATH)
        current_conn_hash = hash(self.connection_string)
        if migration_cache_file.exists():
            try:
                with open(migration_cache_file, "r") as f:
                    cache_data = json.load(f)
                if cache_data.get("connection_string_hash") == current_conn_hash:
                    self.cached_postgres_revision = cache_data.get("revision")
                    logger.info(f"Found cached PostgreSQL migration revision: {self.cached_postgres_revision} for current connection.")
                else:
                    logger.info("PostgreSQL connection string hash mismatch in cache. Ignoring cached revision.")
            except (IOError, json.JSONDecodeError) as e:
                logger.warning(f"Could not read PostgreSQL migration cache file {migration_cache_file}: {e}")
        
        # --- Connection and Engine Setup ---
        self.connection_manager.initialize() 
        logger.info("psycopg2 connection initialized by ConnectionManager.")

        if not self.engine:
            if not self.connection_string: # Should have been caught in __init__
                raise ValueError("Cannot initialize SQLAlchemy engine: Connection string is missing.")
            try:
                self.engine = create_engine(self.connection_string, future=True)
                logger.info("SQLAlchemy engine created successfully.")
            except Exception as e:
                logger.error(f"Failed to create SQLAlchemy engine: {e}")
                raise

        # --- Determine if DB is new/empty for Alembic ---
        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()
        is_new_or_empty_db_for_alembic = 'alembic_version' not in existing_tables
        
        if is_new_or_empty_db_for_alembic:
            logger.info("Database appears new or unmanaged by Alembic ('alembic_version' table missing).")
        else:
            # Check if any model tables are missing, even if alembic_version exists.
            model_table_names = {table_obj.name for table_obj in Base.metadata.sorted_tables}
            missing_model_tables = model_table_names - set(existing_tables)
            if missing_model_tables:
                logger.info(f"Alembic version table exists, but some model tables are missing: {missing_model_tables}. Treating as needing full schema setup.")
                is_new_or_empty_db_for_alembic = True 

        # --- Migration/Schema Setup Logic ---
        if is_new_or_empty_db_for_alembic:
            logger.info("Proceeding with new/empty database setup for PostgreSQL.")
            Base.metadata.create_all(self.engine) 
            logger.info("Schema creation from SQLAlchemy models complete for new PostgreSQL database.")
            
            stamped_revision = stamp_db_head(self.connection_string)
            if stamped_revision:
                try:
                    migration_cache_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(migration_cache_file, "w") as f_cache:
                        json.dump({"connection_string_hash": current_conn_hash, "revision": stamped_revision}, f_cache)
                    logger.info(f"PostgreSQL migration cache updated with stamped head revision: {stamped_revision}")
                except IOError as e:
                    logger.warning(f"Could not write PostgreSQL migration cache file {migration_cache_file}: {e}")
            else:
                logger.warning(f"Could not determine revision after stamping new PostgreSQL database {self.connection_string}. Cache not updated.")
        
        else: # Existing database path
            logger.info("Proceeding with existing PostgreSQL database setup.")
            current_head_script_revision = get_head_revision(self.connection_string)
            logger.info(f"Determined current head script revision for PostgreSQL: {current_head_script_revision}")

            run_migrations_needed = False
            if self.cached_postgres_revision is None:
                logger.info("No cached PostgreSQL revision found. Migrations will be checked.")
                run_migrations_needed = True
            elif current_head_script_revision is None:
                logger.warning("Could not determine head script revision for PostgreSQL. Running migrations as a precaution.")
                run_migrations_needed = True
            elif self.cached_postgres_revision != current_head_script_revision:
                logger.info(f"Cached PostgreSQL revision {self.cached_postgres_revision} differs from head script revision {current_head_script_revision}. Migrations will run.")
                run_migrations_needed = True
            else:
                logger.info(f"Cached PostgreSQL revision {self.cached_postgres_revision} matches head script revision. Migrations will be skipped.")

            if run_migrations_needed:
                logger.info("Running migrations for existing PostgreSQL database.")
                new_db_revision_after_migration = run_migrations(db_url=self.connection_string)
                logger.info(f"Migrations completed for PostgreSQL. Reported database revision: {new_db_revision_after_migration}")
                if new_db_revision_after_migration:
                    try:
                        migration_cache_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(migration_cache_file, "w") as f_cache:
                            json.dump({"connection_string_hash": current_conn_hash, "revision": new_db_revision_after_migration}, f_cache)
                        logger.info(f"PostgreSQL migration cache updated to revision: {new_db_revision_after_migration}")
                    except IOError as e:
                        logger.warning(f"Could not write PostgreSQL migration cache file {migration_cache_file}: {e}")
                else:
                    logger.warning("run_migrations (PostgreSQL) did not return a revision. Cache not updated.")
            
            # After potential migrations, ensure all current model tables exist.
            # This mirrors the original logic of calling Base.metadata.create_all after run_migrations.
            inspector_after_ops = inspect(self.engine) 
            existing_tables_after_ops = inspector_after_ops.get_table_names()
            missing_model_tables_after_ops = []
            for table_obj in Base.metadata.sorted_tables:
                if table_obj.name not in existing_tables_after_ops:
                    missing_model_tables_after_ops.append(table_obj.name)
            
            if missing_model_tables_after_ops:
                logger.info(f"Model tables missing after migrations/checks: {missing_model_tables_after_ops}. Running Base.metadata.create_all().")
                Base.metadata.create_all(self.engine)
                logger.info("Schema update from SQLAlchemy models complete after migrations/checks for PostgreSQL.")
            else:
                logger.info("All model tables exist after migrations/checks for PostgreSQL. Skipping Base.metadata.create_all().")
        
        logger.info("PostgreSQLBackend initialization complete.")


    def close(self) -> None:
        """
        Closes the psycopg2 connection and disposes of the SQLAlchemy engine.
        """
        self.connection_manager.close() # Closes the psycopg2 connection
        if self.engine:
            logger.info("Disposing SQLAlchemy engine.")
            self.engine.dispose()
            self.engine = None

    def insert_usage(self, entry: UsageEntry) -> None:
        self.data_inserter.insert_usage(entry)

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        self._ensure_connected()
        self.limit_manager.insert_usage_limit(limit)

    def delete_usage_limit(self, limit_id: int) -> None:
        self.data_deleter.delete_usage_limit(limit_id)

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return self.query_executor.get_period_stats(start, end)

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        return self.query_executor.get_model_stats(start, end)

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        return self.query_executor.get_model_rankings(start, end)

    def tail(self, n: int = 10) -> List[UsageEntry]:
        return self.query_executor.tail(n)

    def purge(self) -> None:
        self.data_deleter.purge()

    def get_usage_limits(
            self,
            scope: Optional[LimitScope] = None,
            model: Optional[str] = None,
            username: Optional[str] = None,
            caller_name: Optional[str] = None,
            project_name: Optional[str] = None,
            filter_project_null: Optional[bool] = None,
            filter_username_null: Optional[bool] = None,
            filter_caller_name_null: Optional[bool] = None) -> List[UsageLimitDTO]:
        self._ensure_connected()
        return self.limit_manager.get_usage_limits(
            scope=scope,
            model=model,
            username=username,
            caller_name=caller_name,
            project_name=project_name,
            filter_project_null=filter_project_null,
            filter_username_null=filter_username_null,
            filter_caller_name_null=filter_caller_name_null
        )

    def get_accounting_entries_for_quota(
            self,
            start_time: datetime,
            limit_type: LimitType,
            model: Optional[str] = None,
            username: Optional[str] = None,
            caller_name: Optional[str] = None,
            project_name: Optional[str] = None,
            filter_project_null: Optional[bool] = None) -> float:
        self._ensure_connected()
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        if limit_type == LimitType.REQUESTS:
            agg_field = "COUNT(*)"
        elif limit_type == LimitType.INPUT_TOKENS:
            agg_field = "COALESCE(SUM(prompt_tokens), 0)"
        elif limit_type == LimitType.OUTPUT_TOKENS:
            agg_field = "COALESCE(SUM(completion_tokens), 0)"
        elif limit_type == LimitType.COST:
            agg_field = "COALESCE(SUM(cost), 0.0)"
        else:
            logger.error(f"Unsupported LimitType for quota aggregation: {limit_type}")
            raise ValueError(f"Unsupported LimitType for quota aggregation: {limit_type}")

        base_query = f"SELECT {agg_field} AS aggregated_value FROM accounting_entries"
        conditions = ["timestamp >= %s"]
        params: List[Any] = [start_time]

        if model:
            conditions.append("model_name = %s") # Assuming column is model_name as in some other backends
            params.append(model)
        if username:
            conditions.append("username = %s")
            params.append(username)
        if caller_name:
            conditions.append("caller_name = %s")
            params.append(caller_name)
        
        if project_name is not None:
            conditions.append("project = %s")
            params.append(project_name)
        if filter_project_null is True:
            conditions.append("project IS NULL")
        if filter_project_null is False:
            conditions.append("project IS NOT NULL")

        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += ";"

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, tuple(params))
                result = cur.fetchone()
                if result and result[0] is not None:
                    return float(result[0])
                return 0.0
        except psycopg2.Error as e:
            logger.error(f"Error getting accounting entries for quota (type: {limit_type.value}): {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting accounting entries for quota (type: {limit_type.value}): {e}")
            raise

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        self._ensure_connected()
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        if not query.lstrip().upper().startswith("SELECT"):
            logger.error(f"Attempted to execute non-SELECT query: {query}")
            raise ValueError("Only SELECT queries are allowed for execution via this method.")
        results = []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                results = [dict(row) for row in cur.fetchall()]
            logger.info(f"Successfully executed custom query. Rows returned: {len(results)}")
            return results
        except psycopg2.Error as e:
            logger.error(f"Error executing query '{query}': {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred executing query '{query}': {e}")
            raise

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        return self.query_executor.get_usage_costs(user_id, start_date, end_date)

    def set_usage_limit(
            self,
            user_id: str,
            limit_amount: float,
            limit_type_str: str = "COST") -> None:
        self.query_executor.set_usage_limit(user_id, limit_amount, limit_type_str)

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimitDTO]]:
        self._ensure_connected()
        return self.limit_manager.get_usage_limit(user_id, project_name=None)

    def _ensure_connected(self) -> None:
        self.connection_manager.ensure_connected()

    def initialize_audit_log_schema(self) -> None:
        self.connection_manager.ensure_connected()
        logger.info("Audit log schema initialization check (delegated to main initialize).")

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        self.connection_manager.ensure_connected()
        assert self.conn is not None, "Database connection is not established for logging audit event."
        try:
            self.data_inserter.insert_audit_log_event(entry)
            self.conn.commit()
            logger.info(f"Audit event logged successfully for user '{entry.user_name}', app '{entry.app_name}'.")
        except psycopg2.Error as e: # Specific psycopg2 error
            logger.error(f"Database error logging audit event: {e}")
            if self.conn and not self.conn.closed:
                try:
                    self.conn.rollback()
                    logger.info("Transaction rolled back due to error logging audit event.")
                except psycopg2.Error as rb_err: # Specific psycopg2 error during rollback
                    logger.error(f"Error during rollback attempt: {rb_err}")
            raise RuntimeError(f"Failed to log audit event due to database error: {e}") from e
        except Exception as e: # Catch other errors
            logger.error(f"An unexpected error occurred logging audit event: {e}")
            if self.conn and not self.conn.closed: # Check conn before rollback
                try:
                    self.conn.rollback()
                    logger.info("Transaction rolled back due to unexpected error logging audit event.")
                except psycopg2.Error as rb_err: # Specific psycopg2 error during rollback
                    logger.error(f"Error during rollback attempt: {rb_err}")
            raise RuntimeError(f"Failed to log audit event due to unexpected error: {e}") from e


    def get_audit_log_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        app_name: Optional[str] = None,
        user_name: Optional[str] = None,
        project: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: Optional[int] = None,
        # filter_project_null: Optional[bool] = None, # Parameter was not used by underlying query_executor
    ) -> List[AuditLogEntry]:
        self.connection_manager.ensure_connected()
        assert self.conn is not None, "Database connection is not established for retrieving audit log entries."
        try:
            entries = self.query_executor.get_audit_log_entries(
                start_date=start_date,
                end_date=end_date,
                app_name=app_name,
                user_name=user_name,
                project=project,
                log_type=log_type,
                limit=limit,
            )
            logger.info(f"Retrieved {len(entries)} audit log entries.")
            return entries
        except psycopg2.Error as e:
            logger.error(f"Database error retrieving audit log entries: {e}")
            raise RuntimeError(f"Failed to retrieve audit log entries due to database error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving audit log entries: {e}")
            raise RuntimeError(f"Unexpected error occurred while retrieving audit log entries: {e}") from e
