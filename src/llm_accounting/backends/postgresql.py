import logging
import os
import psycopg2
import psycopg2.extras  # For RealDictCursor
import psycopg2.extensions  # For connection type
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from sqlalchemy import create_engine, text, inspect
from llm_accounting.models.base import Base

from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry
from ..models.limits import UsageLimitDTO, LimitScope, LimitType
from ..db_migrations import run_migrations # Import run_migrations

from .postgresql_backend_parts.connection_manager import ConnectionManager
from .postgresql_backend_parts.schema_manager import SchemaManager
from .postgresql_backend_parts.data_inserter import DataInserter
from .postgresql_backend_parts.data_deleter import DataDeleter
from .postgresql_backend_parts.query_executor import QueryExecutor
from .postgresql_backend_parts.limit_manager import LimitManager

logger = logging.getLogger(__name__)


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
        logger.info("PostgreSQLBackend initialized with connection string.")

        self.connection_manager = ConnectionManager(self)
        self.schema_manager = SchemaManager(self)
        self.data_inserter = DataInserter(self)
        self.data_deleter = DataDeleter(self)
        self.query_executor = QueryExecutor(self)
        self.limit_manager = LimitManager(self, self.data_inserter)

    def initialize(self) -> None:
        """
        Connects to the PostgreSQL database, sets up the SQLAlchemy engine,
        and ensures the schema is created via SQLAlchemy models if tables are missing.
        The psycopg2 connection is also initialized for existing components.
        """
        self.connection_manager.initialize() 
        logger.info("psycopg2 connection initialized by ConnectionManager.")

        if not self.engine:
            if not self.connection_string:
                raise ValueError("Cannot initialize SQLAlchemy engine: Connection string is missing.")
            try:
                self.engine = create_engine(self.connection_string, future=True)
                logger.info("SQLAlchemy engine created successfully.")
            except Exception as e:
                logger.error(f"Failed to create SQLAlchemy engine: {e}")
                raise

        # Run database migrations
        assert self.connection_string is not None, "Connection string must be set before running migrations."
        run_migrations(db_url=self.connection_string)

        # Ensure schema is created via SQLAlchemy models if tables are missing.
        # This handles initial setup for new databases.
        if self.engine:
            try:
                inspector = inspect(self.engine)
                existing_tables = inspector.get_table_names()
                
                tables_to_create = []
                for table_obj in Base.metadata.sorted_tables:
                    if table_obj.name not in existing_tables:
                         tables_to_create.append(table_obj.name)

                if tables_to_create:
                    logger.info(f"New tables to create based on SQLAlchemy models: {tables_to_create}. Creating schema...")
                    Base.metadata.create_all(self.engine)
                    logger.info("Schema creation/update from SQLAlchemy models complete.")
                else:
                    logger.info("All tables defined in SQLAlchemy models already exist. Schema creation via Base.metadata.create_all skipped.")
            except Exception as e:
                logger.error(f"Error during schema inspection or creation with SQLAlchemy: {e}")
                raise
        else:
            logger.error("SQLAlchemy engine not available. Cannot perform schema check/creation.")
            raise RuntimeError("SQLAlchemy engine could not be initialized.")

    def close(self) -> None:
        """
        Closes the psycopg2 connection and disposes of the SQLAlchemy engine.
        """
        self.connection_manager.close() # Closes the psycopg2 connection
        if self.engine:
            logger.info("Disposing SQLAlchemy engine.")
            self.engine.dispose()
            self.engine = None

    # _create_schema_if_not_exists and _create_tables methods are removed from PostgreSQLBackend
    # as this responsibility is now with initialize() using SQLAlchemy and Alembic for migrations.

    def insert_usage(self, entry: UsageEntry) -> None:
        self.data_inserter.insert_usage(entry)

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """
        Inserts a usage limit into the usage_limits table.
        Delegates to LimitManager.
        """
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
        """
        Retrieves usage limits (as UsageLimitData objects) from the `usage_limits` table
        based on specified filter criteria. Delegates to LimitManager.
        """
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
            conditions.append("model_name = %s")
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
        """
        A simplified way to set a usage limit for a user.
        Delegates to QueryExecutor.
        NOTE: This method is distinct from the BaseBackend's insert_usage_limit.
              It's a convenience method. The primary method for inserting limits
              is now `insert_usage_limit(self, limit_data: UsageLimitData)`.
              This one might need to be refactored or deprecated.
        """
        self.query_executor.set_usage_limit(user_id, limit_amount, limit_type_str)

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimitDTO]]:
        """
        Retrieves all usage limits (as UsageLimitData) for a specific user.
        Delegates to LimitManager.
        NOTE: This method is distinct from BaseBackend's get_usage_limits.
              It's a convenience method.
        """
        self._ensure_connected()
        return self.limit_manager.get_usage_limit(user_id, project_name=None)

    def _ensure_connected(self) -> None:
        self.connection_manager.ensure_connected()

    # Audit Log Methods Implementation

    def initialize_audit_log_schema(self) -> None:
        """
        Ensures the audit log schema is initialized.
        In this backend, the main initialize() method handles all schema creation.
        This method primarily ensures the connection is active.
        """
        self.connection_manager.ensure_connected()
        # self.schema_manager._create_schema_if_not_exists() # This is called by initialize()
        logger.info("Audit log schema initialization check (delegated to main initialize).")

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        """
        Logs an audit event to the database.
        Manages connection, transaction commit, and rollback.
        """
        self.connection_manager.ensure_connected()
        assert self.conn is not None, "Database connection is not established for logging audit event."

        try:
            self.data_inserter.insert_audit_log_event(entry)
            self.conn.commit()
            logger.info(f"Audit event logged successfully for user '{entry.user_name}', app '{entry.app_name}'.")
        except psycopg2.Error as e:
            logger.error(f"Database error logging audit event: {e}")
            if self.conn and not self.conn.closed:
                try:
                    self.conn.rollback()
                    logger.info("Transaction rolled back due to error logging audit event.")
                except psycopg2.Error as rb_err:
                    logger.error(f"Error during rollback attempt: {rb_err}")
            # Consider re-raising a more generic error or a specific application error
            raise RuntimeError(f"Failed to log audit event due to database error: {e}") from e
        except Exception as e:
            logger.error(f"Failed to log audit event due to database error: {e}")
            if self.conn and not self.conn.closed:
                try:
                    self.conn.rollback()
                    logger.info("Transaction rolled back due to error logging audit event.")
                except psycopg2.Error as rb_err:
                    logger.error(f"Error during rollback attempt: {rb_err}")
            raise RuntimeError(f"Failed to log audit event due to database error: {e}") from e

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
        """
        Retrieves audit log entries based on specified filter criteria.
        Delegates to QueryExecutor and manages connection.
        """
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
            # For read operations, rollback is typically not needed unless part of a larger transaction
            raise RuntimeError(f"Failed to retrieve audit log entries due to database error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving audit log entries: {e}")
            raise RuntimeError(f"Unexpected error occurred while retrieving audit log entries: {e}") from e
