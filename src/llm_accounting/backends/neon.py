import logging
import os
import psycopg2
import psycopg2.extras # For RealDictCursor
import psycopg2.extensions # For connection type
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from .base import BaseBackend, UsageEntry, UsageStats 
from ..models.limits import UsageLimit, LimitScope, LimitType, TimeInterval

from .neon_backend_parts.connection_manager import ConnectionManager
from .neon_backend_parts.schema_manager import SchemaManager
from .neon_backend_parts.data_inserter import DataInserter
from .neon_backend_parts.data_deleter import DataDeleter
from .neon_backend_parts.query_executor import QueryExecutor

logger = logging.getLogger(__name__)

class NeonBackend(BaseBackend):
    conn: Optional[psycopg2.extensions.connection] = None
    """
    A backend for llm-accounting that uses a PostgreSQL database, specifically
    tailored for Neon serverless Postgres but compatible with standard PostgreSQL instances.
    """

    def __init__(self, neon_connection_string: Optional[str] = None):
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

    def initialize(self) -> None:
        self.connection_manager.initialize()
        self.schema_manager._create_schema_if_not_exists()

    def close(self) -> None:
        self.connection_manager.close()

    def _create_schema_if_not_exists(self) -> None:
        self.schema_manager._create_schema_if_not_exists()

    def _create_tables(self) -> None:
        self.schema_manager._create_tables()

    def insert_usage(self, entry: UsageEntry) -> None:
        self.data_inserter.insert_usage(entry)

    def insert_usage_limit(self, limit: UsageLimit) -> None:
        self.data_inserter.insert_usage_limit(limit)

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
        self.data_deleter.purge() # This should also delete from usage_limits

    def get_usage_limits(self,
                         scope: Optional[LimitScope] = None,
                         model: Optional[str] = None,
                         username: Optional[str] = None,
                         caller_name: Optional[str] = None,
                         project_name: Optional[str] = None) -> List[UsageLimit]: # Added project_name
        self._ensure_connected()
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        # Select all relevant fields including project_name
        base_query = "SELECT id, scope, limit_type, model_name, username, caller_name, project_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits"
        conditions = []
        params = []

        if scope:
            conditions.append("scope = %s")
            params.append(scope.value)
        if model:
            conditions.append("model_name = %s")
            params.append(model)
        if username:
            conditions.append("username = %s")
            params.append(username)
        if caller_name:
            conditions.append("caller_name = %s")
            params.append(caller_name)
        if project_name: # Filter by project_name
            conditions.append("project_name = %s")
            params.append(project_name)
        
        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC;"

        limits = []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                for row_dict in cur:
                    data = dict(row_dict)
                    data['scope'] = LimitScope(data['scope'])
                    data['limit_type'] = LimitType(data['limit_type'])
                    data['interval_unit'] = TimeInterval(data['interval_unit'])
                    
                    if 'model_name' in data and 'model' not in data:
                         data['model'] = data.pop('model_name')
                    # project_name is already correctly named from DB

                    limits.append(UsageLimit(**data))
            return limits
        except psycopg2.Error as e:
            logger.error(f"Error getting usage limits: {e}")
            raise
        except ValueError as e:
            logger.error(f"Error converting database value to Enum for usage limits: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting usage limits: {e}")
            raise

    def get_accounting_entries_for_quota(self,
                                   start_time: datetime,
                                   limit_type: LimitType,
                                   model: Optional[str] = None,
                                   username: Optional[str] = None,
                                   caller_name: Optional[str] = None,
                                   project_name: Optional[str] = None) -> float: # Added project_name
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
        if project_name: # Filter by project if provided for accounting_entries
            conditions.append("project = %s") # Column in accounting_entries is 'project'
            params.append(project_name)
        # If project_name is None and we need to filter for entries with project IS NULL:
        # elif project_name is None and some_condition_to_filter_null_projects:
        #     conditions.append("project IS NULL")
        # This logic depends on how QuotaService calls this. For now, only filter if project_name is explicitly given.

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

    def set_usage_limit(self, user_id: str, limit_amount: float, limit_type_str: str = "COST") -> None:
        self.query_executor.set_usage_limit(user_id, limit_amount, limit_type_str)

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimit]]:
        return self.query_executor.get_usage_limit(user_id)

    def _ensure_connected(self) -> None:
        self.connection_manager.ensure_connected()
