import logging
import os
import psycopg2
import psycopg2.extras  # For RealDictCursor
import psycopg2.extensions  # For connection type
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from .base import BaseBackend, UsageEntry, UsageStats
from ..models.limits import UsageLimitDTO, LimitScope, LimitType

from .neon_backend_parts.connection_manager import ConnectionManager
from .neon_backend_parts.schema_manager import SchemaManager
from .neon_backend_parts.data_inserter import DataInserter
from .neon_backend_parts.data_deleter import DataDeleter
from .neon_backend_parts.query_executor import QueryExecutor
from .neon_backend_parts.limit_manager import LimitManager  # Import LimitManager

logger = logging.getLogger(__name__)


class NeonBackend(BaseBackend):
    conn: Optional[psycopg2.extensions.connection] = None
    """
    A backend for llm-accounting that uses a PostgreSQL database, specifically
    tailored for Neon serverless Postgres but compatible with standard PostgreSQL instances.
    """

    def __init__(self, neon_connection_string: Optional[str] = None):
        """
        Initializes the NeonBackend.
        """
        if neon_connection_string:
            self.connection_string = neon_connection_string
        else:
            self.connection_string = os.environ.get("NEON_CONNECTION_STRING")

        if not self.connection_string:
            raise ValueError(
                "Neon connection string not provided and NEON_CONNECTION_STRING "
                "environment variable is not set."
            )
        self.conn = None
        logger.info("NeonBackend initialized with connection string.")

        self.connection_manager = ConnectionManager(self)
        self.schema_manager = SchemaManager(self)
        self.data_inserter = DataInserter(self)
        self.data_deleter = DataDeleter(self)
        self.query_executor = QueryExecutor(self)
        # Instantiate LimitManager, passing the backend instance and data_inserter instance
        self.limit_manager = LimitManager(self, self.data_inserter)

    def initialize(self) -> None:
        """
        Connects to the Neon database and sets up the schema.
        """
        self.connection_manager.initialize()
        self.schema_manager._create_schema_if_not_exists()

    def close(self) -> None:
        """
        Closes the connection to the Neon database.
        """
        self.connection_manager.close()

    def _create_schema_if_not_exists(self) -> None:
        self.schema_manager._create_schema_if_not_exists()

    def _create_tables(self) -> None:
        self.schema_manager._create_tables()

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
