import logging
import psycopg2
from datetime import datetime

from ...models.limits import UsageLimit
from ..base import UsageEntry, AuditLogEntry  # Added AuditLogEntry

logger = logging.getLogger(__name__)


class DataInserter:
    def __init__(self, backend_instance):
        self.backend = backend_instance

    def insert_usage(self, entry: UsageEntry) -> None:
        """
        Inserts a usage entry into the accounting_entries table.

        Args:
            entry: A `UsageEntry` dataclass object containing the data to be inserted.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

        # SQL INSERT statement for accounting_entries table.
        # Uses %s placeholders for parameters to prevent SQL injection.
        sql = """
            INSERT INTO accounting_entries (
                model_name, prompt_tokens, completion_tokens, total_tokens,
                local_prompt_tokens, local_completion_tokens, local_total_tokens,
                cost, execution_time, timestamp, caller_name, username,
                cached_tokens, reasoning_tokens, project
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self.backend.conn.cursor() as cur:
                cur.execute(sql, (
                    entry.model, entry.prompt_tokens, entry.completion_tokens, entry.total_tokens,
                    entry.local_prompt_tokens, entry.local_completion_tokens, entry.local_total_tokens,
                    entry.cost, entry.execution_time, entry.timestamp or datetime.now(),
                    entry.caller_name, entry.username, entry.cached_tokens, entry.reasoning_tokens,
                    entry.project
                ))
                self.backend.conn.commit()
            logger.info(f"Successfully inserted usage entry for user '{entry.username}' "
                        f"and model '{entry.model}'.")
        except psycopg2.Error as e:
            logger.error(f"Error inserting usage entry: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred inserting usage entry: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise

    def insert_usage_limit(self, limit: UsageLimit) -> None:
        """
        Inserts a usage limit into the usage_limits table.

        Args:
            limit: A `UsageLimit` dataclass object defining the limit to be inserted.
                   Enum fields (scope, limit_type, interval_unit) are stored as their string values.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

        # SQL INSERT statement for usage_limits table.
        # Enum values are accessed using `.value` for storage as strings.
        sql = """
            INSERT INTO usage_limits (
                scope, limit_type, max_value, interval_unit, interval_value,
                model_name, username, caller_name, project_name, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self.backend.conn.cursor() as cur:
                cur.execute(sql, (
                    limit.scope, limit.limit_type, limit.max_value,
                    limit.interval_unit, limit.interval_value,
                    limit.model, limit.username, limit.caller_name,
                    limit.project_name,  # Added project_name
                    limit.created_at or datetime.now(), limit.updated_at or datetime.now()
                ))
                self.backend.conn.commit()
            logger.info(f"Successfully inserted usage limit for scope '{limit.scope}' "
                        f"and type '{limit.limit_type}'.")
        except psycopg2.Error as e:
            logger.error(f"Error inserting usage limit: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred inserting usage limit: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise

    def insert_audit_log_event(self, entry: AuditLogEntry) -> None:
        """
        Prepares the SQL for inserting an audit log entry.
        The actual execution, connection management, and transaction control (commit/rollback)
        are handled by the calling PostgreSQLBackend method.

        Args:
            entry: An `AuditLogEntry` dataclass object containing the data to be inserted.

        Raises:
            psycopg2.Error: If any error occurs during SQL preparation/execution by the cursor.
            Exception: For any other unexpected errors during the process.
        """
        # self.backend._ensure_connected() is assumed to be called by the PostgreSQLBackend.
        assert self.backend.conn is not None, "Database connection is not established."

        sql = """
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, prompt_text,
                response_text, remote_completion_id, project, session, log_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            entry.timestamp,  # psycopg2 handles datetime objects for TIMESTAMPTZ
            entry.app_name,
            entry.user_name,
            entry.model,
            entry.prompt_text,
            entry.response_text,
            entry.remote_completion_id,
            entry.project,
            entry.session,
            entry.log_type,
        )

        try:
            # The cursor is obtained from the backend's connection.
            # The 'with' statement ensures the cursor is closed after use.
            with self.backend.conn.cursor() as cur:
                cur.execute(sql, params)
            # Commit and rollback are handled by the calling PostgreSQLBackend method.
            logger.info(f"Successfully prepared SQL for audit log event for user '{entry.user_name}', app '{entry.app_name}'.")
        except psycopg2.Error as e:
            logger.error(f"Error preparing SQL for audit log event: {e}")
            # Re-raise to allow the PostgreSQLBackend method to handle transaction control (rollback).
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while preparing SQL for audit log event: {e}")
            # Re-raise to allow the PostgreSQLBackend method to handle transaction control.
            raise

    def insert_quota_rejection(self, session: str, rejection_message: str, created_at: datetime) -> None:
        assert self.backend.conn is not None, "Database connection is not established."
        sql = (
            "INSERT INTO quota_rejections (created_at, session, rejection_message) "
            "VALUES (%s, %s, %s)"
        )
        params = (created_at, session, rejection_message)
        with self.backend.conn.cursor() as cur:
            cur.execute(sql, params)
