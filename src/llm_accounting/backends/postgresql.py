import logging
import os
import psycopg2
import psycopg2.extras
import psycopg2.extensions
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import create_engine, inspect
from llm_accounting.models.base import Base  # Corrected based on original

from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry, UserRecord
from ..models.limits import UsageLimitDTO, LimitScope, LimitType
from ..db_migrations import run_migrations, get_head_revision, stamp_db_head
from ..version_cache import should_run_migrations, update_migration_cache_after_success

from .postgresql_backend_parts.connection_manager import ConnectionManager
from .postgresql_backend_parts.schema_manager import SchemaManager
from .postgresql_backend_parts.data_inserter import DataInserter
from .postgresql_backend_parts.data_deleter import DataDeleter
from .postgresql_backend_parts.query_executor import QueryExecutor
from .postgresql_backend_parts.limit_manager import LimitManager
from .postgresql_backend_parts.project_manager import ProjectManager
from .postgresql_backend_parts.user_manager import UserManager

logger = logging.getLogger(__name__)

POSTGRES_MIGRATION_CACHE_PATH = "data/postgresql_migration_cache.json"


class PostgreSQLBackend(BaseBackend):
    conn: Optional[psycopg2.extensions.connection] = None  # Retained for type hinting, but managed by ConnectionManager

    def __init__(self, postgresql_connection_string: Optional[str] = None):
        if postgresql_connection_string:
            self.connection_string = postgresql_connection_string
        else:
            self.connection_string = os.environ.get("POSTGRESQL_CONNECTION_STRING")

        if not self.connection_string:
            raise ValueError(
                "PostgreSQL connection string not provided and POSTGRESQL_CONNECTION_STRING "
                "environment variable is not set."
            )
        # self.conn is primarily managed by ConnectionManager now.
        # self.engine is initialized in the initialize() method.
        self.engine = None
        logger.debug("PostgreSQLBackend initialized with connection string.")

        self.connection_manager = ConnectionManager(self)
        # self.schema_manager = SchemaManager(self) # Vulture: unused attribute
        self.data_inserter = DataInserter(self)
        self.data_deleter = DataDeleter(self)
        self.query_executor = QueryExecutor(self)
        self.limit_manager = LimitManager(self, self.data_inserter)
        self.project_manager = ProjectManager(self)
        self.user_manager = UserManager(self)


    def _determine_if_new_or_empty_db(self) -> bool:
        if not self.engine:
            logger.error("Engine not initialized before _determine_if_new_or_empty_db call.")
            raise RuntimeError("Database engine must be initialized before determining DB state.")

        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()

        if 'alembic_version' not in existing_tables:
            logger.debug("Database appears new or unmanaged by Alembic ('alembic_version' table missing).")
            return True

        model_table_names = {table_obj.name for table_obj in Base.metadata.sorted_tables}
        missing_model_tables = model_table_names - set(existing_tables)
        if missing_model_tables:
            logger.debug(f"Alembic version table exists, but some model tables are missing: {missing_model_tables}. Treating as needing full schema setup.")
            return True

        return False

    def _setup_new_postgres_db(self, migration_cache_file: Path) -> None:
        logger.info("Proceeding with new/empty database setup for PostgreSQL.")
        assert self.engine is not None
        Base.metadata.create_all(self.engine)
        logger.debug("Schema creation from SQLAlchemy models complete for new PostgreSQL database.")

        stamped_revision = stamp_db_head(self.connection_string)
        if stamped_revision:
            update_migration_cache_after_success(migration_cache_file, stamped_revision)

    def _setup_existing_postgres_db(self, migration_cache_file: Path) -> None:
        logger.debug("Proceeding with existing PostgreSQL database setup.")
        assert self.engine is not None

        current_head_script_revision = get_head_revision(self.connection_string)
        logger.debug(f"Determined current head script revision for PostgreSQL: {current_head_script_revision}")

        if current_head_script_revision is None:
            logger.warning("Could not determine head script revision for PostgreSQL. Running migrations as a precaution.")
            run_migrations_needed = True
        else:
            run_migrations_needed = should_run_migrations(migration_cache_file, current_head_script_revision)

        if run_migrations_needed:
            logger.info("Running migrations for existing PostgreSQL database.")
            new_db_revision_after_migration = run_migrations(db_url=self.connection_string)
            logger.debug(f"Migrations completed for PostgreSQL. Reported database revision: {new_db_revision_after_migration}")
            if new_db_revision_after_migration:
                update_migration_cache_after_success(migration_cache_file, new_db_revision_after_migration)
        else:
            logger.debug("Migrations skipped for PostgreSQL based on package version cache.")

        inspector_after_ops = inspect(self.engine)
        existing_tables_after_ops = inspector_after_ops.get_table_names()
        missing_model_tables_after_ops = [
            table_obj.name for table_obj in Base.metadata.sorted_tables
            if table_obj.name not in existing_tables_after_ops
        ]

        if missing_model_tables_after_ops:
            logger.debug(f"Model tables missing after migrations/checks: {missing_model_tables_after_ops}. Running Base.metadata.create_all().")
            Base.metadata.create_all(self.engine)
            logger.debug("Schema update from SQLAlchemy models complete after migrations/checks for PostgreSQL.")
        else:
            logger.debug("All model tables exist after migrations/checks for PostgreSQL. Skipping Base.metadata.create_all().")

    def initialize(self) -> None:
        logger.debug(f"Initializing PostgreSQLBackend (connection: {self.connection_string[:50]}...)")

        migration_cache_file = Path(POSTGRES_MIGRATION_CACHE_PATH)

        self.connection_manager.initialize()
        self.conn = self.connection_manager.conn  # Keep self.conn in sync for other methods if they use it directly
        logger.debug("psycopg2 connection initialized via ConnectionManager.")

        if not self.engine:
            if not self.connection_string:
                raise ValueError("Cannot initialize SQLAlchemy engine: Connection string is missing.")
            try:
                self.engine = create_engine(self.connection_string, future=True)
                logger.debug("SQLAlchemy engine created successfully.")
            except Exception as e:
                logger.error(f"Failed to create SQLAlchemy engine: {e}")
                raise

        is_new_db = self._determine_if_new_or_empty_db()

        if is_new_db:
            self._setup_new_postgres_db(migration_cache_file)
        else:
            self._setup_existing_postgres_db(migration_cache_file)
        logger.debug("PostgreSQLBackend initialization complete.")

    def close(self) -> None:
        self.connection_manager.close()
        self.conn = None  # Clear the direct reference
        if self.engine:
            logger.debug("Disposing SQLAlchemy engine.")
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
        active_conn = self.connection_manager.conn
        if active_conn is None:
            raise ConnectionError("Database connection is not established.")

        agg_field_map = {
            LimitType.REQUESTS: "COUNT(*)",
            LimitType.INPUT_TOKENS: "COALESCE(SUM(prompt_tokens), 0)",
            LimitType.OUTPUT_TOKENS: "COALESCE(SUM(completion_tokens), 0)",
            LimitType.COST: "COALESCE(SUM(cost), 0.0)",
            # Add other limit types here if necessary
        }
        agg_field = agg_field_map.get(limit_type)
        if agg_field is None:
            logger.error(f"Unsupported LimitType for quota aggregation: {limit_type}")
            raise ValueError(f"Unsupported LimitType for quota aggregation: {limit_type}")

        base_query = f"SELECT {agg_field} AS aggregated_value FROM accounting_entries"  # nosec B608
        conditions: List[str] = []
        params: List[Any] = []

        # Always filter by start_time
        conditions.append("timestamp >= %s")
        params.append(start_time)

        filter_map = {
            "model_name": model,
            "username": username,
            "caller_name": caller_name,
            "project": project_name,
        }

        for column, value in filter_map.items():
            if value is not None:
                conditions.append(f"{column} = %s")
                params.append(value)

        if filter_project_null is True:
            conditions.append("project IS NULL")
        elif filter_project_null is False:
            # This condition is only added if project_name is None,
            # otherwise the specific project_name filter takes precedence.
            if project_name is None:
                conditions.append("project IS NOT NULL")

        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += ";"

        try:
            with active_conn.cursor() as cur:
                cur.execute(query, tuple(params))
                result = cur.fetchone()
                return float(result[0]) if result and result[0] is not None else 0.0
        except psycopg2.Error as e:
            logger.error(f"Error getting accounting entries for quota (type: {limit_type.value}): {e}")
            if active_conn and not active_conn.closed:
                active_conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting accounting entries for quota (type: {limit_type.value}): {e}")
            if active_conn and not active_conn.closed:
                active_conn.rollback()
            raise

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        self._ensure_connected()
        active_conn = self.connection_manager.conn
        if active_conn is None:
            raise ConnectionError("Database connection is not established.")

        if not query.lstrip().upper().startswith("SELECT"):
            logger.error(f"Attempted to execute non-SELECT query: {query}")
            raise ValueError("Only SELECT queries are allowed for execution via this method.")
        results = []
        try:
            with active_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                results = [dict(row) for row in cur.fetchall()]
            logger.info(f"Successfully executed custom query. Rows returned: {len(results)}")
            return results
        except psycopg2.Error as e:
            logger.error(f"Error executing query '{query}': {e}")
            active_conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred executing query '{query}': {e}")
            active_conn.rollback()
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
        self.conn = self.connection_manager.conn  # Keep self.conn in sync

    def initialize_audit_log_schema(self) -> None:
        self._ensure_connected()
        logger.info("Audit log schema initialization check (delegated to main initialize if relevant).")

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        self._ensure_connected()
        active_conn = self.connection_manager.conn
        assert active_conn is not None, "Database connection is not established for logging audit event."
        try:
            self.data_inserter.insert_audit_log_event(entry)
            active_conn.commit()
            logger.info(f"Audit event logged successfully for user '{entry.user_name}', app '{entry.app_name}'.")
        except psycopg2.Error as e:
            logger.error(f"Database error logging audit event: {e}")
            if active_conn and not active_conn.closed:
                try:
                    active_conn.rollback()
                    logger.info("Transaction rolled back due to error logging audit event.")
                except psycopg2.Error as rb_err:
                    logger.error(f"Error during rollback attempt: {rb_err}")
            raise RuntimeError(f"Failed to log audit event due to database error: {e}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred logging audit event: {e}")
            if active_conn and not active_conn.closed:
                try:
                    active_conn.rollback()
                    logger.info("Transaction rolled back due to unexpected error logging audit event.")
                except psycopg2.Error as rb_err:
                    logger.error(f"Error during rollback attempt: {rb_err}")
            raise RuntimeError(f"Failed to log audit event due to unexpected error: {e}") from e

    def log_quota_rejection(self, session: str, rejection_message: str, created_at: Optional[datetime] = None) -> None:
        self._ensure_connected()
        active_conn = self.connection_manager.conn
        assert active_conn is not None
        ts = created_at if created_at is not None else datetime.now(timezone.utc)
        try:
            self.data_inserter.insert_quota_rejection(session, rejection_message, ts)
            active_conn.commit()
        except Exception as e:
            if active_conn and not active_conn.closed:
                active_conn.rollback()
            raise RuntimeError(f"Failed to log quota rejection: {e}") from e

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
        self._ensure_connected()
        active_conn = self.connection_manager.conn
        assert active_conn is not None, "Database connection is not established for retrieving audit log entries."
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
            active_conn.rollback()
            raise RuntimeError(f"Failed to retrieve audit log entries due to database error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving audit log entries: {e}")
            active_conn.rollback()
            raise RuntimeError(f"Unexpected error occurred while retrieving audit log entries: {e}") from e

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
