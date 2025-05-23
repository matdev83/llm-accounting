import logging
import os
import psycopg2
import psycopg2.extras # For RealDictCursor
import psycopg2.extensions # For connection type
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from .base import BaseBackend, UsageEntry, UsageStats # Updated import for UsageEntry and UsageStats
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

    This backend handles the storage and retrieval of LLM API usage data,
    including accounting entries, and usage limits.

    Connection Parameters:
    The database connection string is determined in the following order:
    1.  The `neon_connection_string` argument provided during instantiation.
    2.  The `NEON_CONNECTION_STRING` environment variable.

    If neither is provided, a `ValueError` is raised.

    Key Dependencies:
    -   `psycopg2`: The PostgreSQL adapter for Python used to interact with the database.
    """

    def __init__(self, neon_connection_string: Optional[str] = None):
        """
        Initializes the NeonBackend.

        Args:
            neon_connection_string: The connection string for the Neon database.
                If not provided, it will be read from the NEON_CONNECTION_STRING
                environment variable.

        Raises:
            ValueError: If the connection string is not provided and not found
                in the environment variables.
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

        # Initialize helper classes
        self.connection_manager = ConnectionManager(self)
        self.schema_manager = SchemaManager(self)
        self.data_inserter = DataInserter(self)
        self.data_deleter = DataDeleter(self)
        self.query_executor = QueryExecutor(self)

    def initialize(self) -> None:
        """
        Connects to the Neon database and sets up the schema.
        Delegates to ConnectionManager and SchemaManager.

        Raises:
            ConnectionError: If the connection to the database fails.
        """
        self.connection_manager.initialize()
        self.schema_manager._create_schema_if_not_exists()

    def close(self) -> None:
        """
        Closes the connection to the Neon database.
        Delegates to ConnectionManager.
        """
        self.connection_manager.close()

    def _create_schema_if_not_exists(self) -> None:
        """
        Ensures the necessary database schema (tables) exists.
        Delegates to SchemaManager.
        """
        self.schema_manager._create_schema_if_not_exists()

    def _create_tables(self) -> None:
        """
        Creates the database tables (`accounting_entries`, `usage_limits`)
        if they do not already exist in the PostgreSQL database.
        Delegates to SchemaManager.
        """
        self.schema_manager._create_tables()

    def insert_usage(self, entry: UsageEntry) -> None:
        """
        Inserts a usage entry into the accounting_entries table.
        Delegates to DataInserter.
        """
        self.data_inserter.insert_usage(entry)

    def insert_usage_limit(self, limit: UsageLimit) -> None:
        """
        Inserts a usage limit into the usage_limits table.
        Delegates to DataInserter.
        """
        self.data_inserter.insert_usage_limit(limit)

    def delete_usage_limit(self, limit_id: int) -> None:
        """
        Deletes a usage limit entry by its ID from the usage_limits table.
        Delegates to DataDeleter.
        """
        self.data_deleter.delete_usage_limit(limit_id)

    # --- Implemented methods as per subtask ---

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """
        Calculates aggregated usage statistics from `accounting_entries` for a given time period.
        Delegates to QueryExecutor.
        """
        return self.query_executor.get_period_stats(start, end)

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        """
        Calculates aggregated usage statistics for each model within a given time period.
        Delegates to QueryExecutor.
        """
        return self.query_executor.get_model_stats(start, end)

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        """
        Ranks models based on various aggregated metrics (total tokens, cost, etc.)
        within a given time period.
        Delegates to QueryExecutor.
        """
        return self.query_executor.get_model_rankings(start, end)

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """
        Retrieves the last N usage entries from the `accounting_entries` table.
        Delegates to QueryExecutor.
        """
        return self.query_executor.tail(n)

    def purge(self) -> None:
        """
        Deletes all data from `accounting_entries`, and `usage_limits` tables.
        Delegates to DataDeleter.
        """
        self.data_deleter.purge()

    def get_usage_limits(self,
                         scope: Optional[LimitScope] = None,
                         model: Optional[str] = None,
                         username: Optional[str] = None,
                         caller_name: Optional[str] = None) -> List[UsageLimit]:
        """
        Retrieves usage limits from the `usage_limits` table based on specified filter criteria.

        Allows filtering by `scope`, `model_name`, `username`, and `caller_name`.
        Results are ordered by `created_at` in descending order.
        Enum values stored as strings in the DB are converted back to their Enum types.

        Args:
            scope: Optional `LimitScope` enum to filter by.
            model_name: Optional model name string to filter by. (Note: `UsageLimit` dataclass uses `model` field)
            username: Optional username string to filter by.
            caller_name: Optional caller name string to filter by.

        Returns:
            A list of `UsageLimit` objects matching the filters. Returns an empty list if no
            limits match or if no filters are provided and the table is empty.

        Raises:
            ConnectionError: If the database connection is not active.
            ValueError: If a value from the database cannot be converted to its corresponding Enum type.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self._ensure_connected()
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        base_query = "SELECT * FROM usage_limits"
        conditions = []
        params = []

        # Dynamically build the WHERE clause based on provided filters.
        conditions = []
        params = []

        if scope:
            conditions.append("scope = %s")
            params.append(scope.value) # Store enum by its value.
        if model:
            conditions.append("model_name = %s") # DB column is model_name
            params.append(model)
        if username:
            conditions.append("username = %s")
            params.append(username)
        if caller_name:
            conditions.append("caller_name = %s")
            params.append(caller_name)

        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC;" # Most recent limits first.

        limits = []
        try:
            # Uses RealDictCursor for easy mapping to UsageLimit dataclass.
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                for row_dict in cur:
                    data = dict(row_dict) # Make a mutable copy.
                    # Convert string representations from DB back to Enum objects.
                    # This might raise ValueError if DB data is inconsistent with Enum definitions.
                    data['scope'] = LimitScope(data['scope'])
                    data['limit_type'] = LimitType(data['limit_type'])
                    data['interval_unit'] = TimeInterval(data['interval_unit'])
                    
                    # The UsageLimit dataclass expects a field 'model', but the DB stores it as 'model_name'.
                    # This maps 'model_name' from the DB row to the 'model' field for dataclass instantiation.
                    if 'model_name' in data and 'model' not in data:
                         data['model'] = data.pop('model_name')

                    limits.append(UsageLimit(**data))
            return limits
        except psycopg2.Error as e:
            logger.error(f"Error getting usage limits: {e}")
            raise
        except ValueError as e: # Handles errors from Enum string conversion.
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
                                   caller_name: Optional[str] = None) -> float:
        """
        Aggregates API request data from `accounting_entries` for quota checking purposes.

        This method calculates a sum or count based on the `limit_type` (e.g., total cost,
        number of requests, total prompt/completion tokens) since a given `start_time`.
        It can be filtered by `model_name`, `username`, and `caller_name`.

        Args:
            start_time: The `datetime` from which to start aggregating data (inclusive).
            limit_type: The `LimitType` enum indicating what to aggregate (e.g., COST, REQUESTS).
            model_name: Optional model name to filter requests by.
            username: Optional username to filter requests by.
            caller_name: Optional caller name to filter requests by.

        Returns:
            The aggregated float value (e.g., total cost, count of requests).
            Returns 0.0 if no matching requests are found.

        Raises:
            ConnectionError: If the database connection is not active.
            ValueError: If an unsupported `limit_type` is provided.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self._ensure_connected()
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        # Determine the SQL aggregation function based on the limit_type.
        if limit_type == LimitType.REQUESTS:
            agg_field = "COUNT(*)"
        elif limit_type == LimitType.INPUT_TOKENS:
            agg_field = "COALESCE(SUM(prompt_tokens), 0)" # Sum of prompt tokens, 0 if none.
        elif limit_type == LimitType.OUTPUT_TOKENS:
            agg_field = "COALESCE(SUM(completion_tokens), 0)" # Sum of completion tokens, 0 if none.
        elif limit_type == LimitType.COST:
            agg_field = "COALESCE(SUM(cost), 0.0)" # Sum of costs, 0.0 if none.
        else:
            logger.error(f"Unsupported LimitType for quota aggregation: {limit_type}")
            raise ValueError(f"Unsupported LimitType for quota aggregation: {limit_type}")

        base_query = f"SELECT {agg_field} AS aggregated_value FROM accounting_entries"
        # Build dynamic WHERE clause.
        conditions = ["timestamp >= %s"] # Always filter by start_time.
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

        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += ";"

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, tuple(params))
                result = cur.fetchone() # Fetches the single aggregated value.
                if result and result[0] is not None:
                    return float(result[0])
                return 0.0 # Should be covered by COALESCE, but as a fallback.
        except psycopg2.Error as e:
            logger.error(f"Error getting accounting entries for quota (type: {limit_type.value}): {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting accounting entries for quota (type: {limit_type.value}): {e}")
            raise

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes a given read-only SQL query (must be SELECT) and returns the results.

        This method is intended for advanced use cases where custom querying is needed.
        It uses `psycopg2.extras.RealDictCursor` to return rows as dictionaries.

        Args:
            query: The SQL SELECT query string to execute. Parameters should be
                   already embedded in the query string if needed (use with caution
                   to avoid SQL injection if query string components are from external input).

        Returns:
            A list of dictionaries, where each dictionary represents a row from the query result.

        Raises:
            ConnectionError: If the database connection is not active.
            ValueError: If the provided query is not a SELECT query.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self._ensure_connected()
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        # Basic validation to allow only SELECT queries.
        if not query.lstrip().upper().startswith("SELECT"):
            logger.error(f"Attempted to execute non-SELECT query: {query}")
            raise ValueError("Only SELECT queries are allowed for execution via this method.")

        results = []
        try:
            # Using RealDictCursor to get results as dictionaries.
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                results = [dict(row) for row in cur.fetchall()] # Convert RealDictRow objects to standard dicts.
            logger.info(f"Successfully executed custom query. Rows returned: {len(results)}")
            return results
        except psycopg2.Error as e:
            logger.error(f"Error executing query '{query}': {e}")
            # For SELECT queries, rollback is typically not necessary unless a transaction was
            # implicitly started and an error occurred mid-fetch, which is less common.
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred executing query '{query}': {e}")
            raise

    # --- Implementation of methods from BaseBackend ---

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        """
        Calculates the total usage costs for a specific user from `accounting_entries`
        within an optional date range.
        Delegates to QueryExecutor.
        """
        return self.query_executor.get_usage_costs(user_id, start_date, end_date)

    def set_usage_limit(self, user_id: str, limit_amount: float, limit_type_str: str = "COST") -> None:
        """
        A simplified way to set a usage limit for a user. It creates a `UsageLimit` object
        with `USER` scope and `MONTHLY` interval by default, then calls `insert_usage_limit`.
        Delegates to QueryExecutor.
        """
        self.query_executor.set_usage_limit(user_id, limit_amount, limit_type_str)

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimit]]:
        """
        Retrieves all usage limits defined for a specific user.
        Delegates to QueryExecutor.
        """
        return self.query_executor.get_usage_limit(user_id)

    def _ensure_connected(self) -> None:
        """
        Ensures the Neon backend has an active connection.
        Initializes the connection if it's None or closed.
        Raises ConnectionError if initialization fails.
        Delegates to ConnectionManager.
        """
        self.connection_manager.ensure_connected()
