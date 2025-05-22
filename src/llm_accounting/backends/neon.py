import logging
import os
import psycopg2
import psycopg2.extras # For RealDictCursor
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from .base import BaseBackend, UsageEntry, UsageStats # Updated import for UsageEntry and UsageStats
from ..models.request import APIRequest
from ..models.limits import UsageLimit, LimitScope, LimitType, TimeInterval

logger = logging.getLogger(__name__)

class NeonBackend(BaseBackend):
    """
    A backend for llm-accounting that uses a PostgreSQL database, specifically
    tailored for Neon serverless Postgres but compatible with standard PostgreSQL instances.

    This backend handles the storage and retrieval of LLM API usage data,
    including accounting entries, API request details, and usage limits.

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

    def initialize(self) -> None:
        """
        Connects to the Neon database and sets up the schema.

        Raises:
            ConnectionError: If the connection to the database fails during `psycopg2.connect`
                             or if schema creation fails.
        """
        try:
            logger.info(f"Attempting to connect to Neon/PostgreSQL database using the provided connection string.")
            # Establish the connection to the PostgreSQL database.
            self.conn = psycopg2.connect(self.connection_string)
            logger.info("Successfully connected to Neon/PostgreSQL database.")
            # Ensure the necessary database schema (tables) exists.
            self._create_schema_if_not_exists()
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to Neon/PostgreSQL database: {e}")
            self.conn = None # Ensure conn is None if connection failed
            # The original psycopg2.Error 'e' is included in the ConnectionError for more detailed debugging.
            raise ConnectionError(f"Failed to connect to Neon/PostgreSQL database (see logs for details).") from e
        # No specific error handling for _create_schema_if_not_exists here, as it raises its own errors.

    def close(self) -> None:
        """
        Closes the connection to the Neon database.
        """
        if self.conn and not self.conn.closed:
            self.conn.close()
            logger.info("Closed connection to Neon database.")
        else:
            logger.info("Connection to Neon database was already closed or not established.")
        self.conn = None

    def _create_schema_if_not_exists(self) -> None:
        """
        Ensures the necessary database schema (tables) exists.
        """
        self._create_tables()

    def _create_tables(self) -> None:
        """
        Creates the database tables (`accounting_entries`, `api_requests`, `usage_limits`)
        if they do not already exist in the PostgreSQL database.

        Uses `CREATE TABLE IF NOT EXISTS` to avoid errors if tables are already present.
        The schema is designed to store usage data, request details, and limits,
        mapping directly to the `UsageEntry`, `APIRequest`, and `UsageLimit` dataclasses.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during DDL execution (and is re-raised).
            Exception: For any other unexpected errors during table creation (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot create tables, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # SQL DDL commands for creating tables.
        # These correspond to UsageEntry, APIRequest, and UsageLimit dataclasses.
        commands = (
            """
            CREATE TABLE IF NOT EXISTS accounting_entries (
                id SERIAL PRIMARY KEY, -- Auto-incrementing integer primary key
                model_name VARCHAR(255) NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                local_prompt_tokens INTEGER,
                local_completion_tokens INTEGER,
                local_total_tokens INTEGER,
                cost DOUBLE PRECISION NOT NULL,       -- Cost of the API call
                execution_time DOUBLE PRECISION,      -- Execution time in seconds
                timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Timestamp of the entry
                caller_name VARCHAR(255),             -- Optional identifier for the calling function/module
                username VARCHAR(255),                -- Optional identifier for the user
                cached_tokens INTEGER,                -- Number of tokens retrieved from cache
                reasoning_tokens INTEGER              -- Number of tokens used for reasoning/tool use
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS api_requests (
                id SERIAL PRIMARY KEY,
                model_name VARCHAR(255) NOT NULL,
                username VARCHAR(255),
                caller_name VARCHAR(255),
                input_tokens INTEGER,                 -- Tokens in the input/prompt
                output_tokens INTEGER,                -- Tokens in the output/completion
                cost DOUBLE PRECISION,                -- Cost associated with this specific request
                timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Timestamp of the request
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS usage_limits (
                id SERIAL PRIMARY KEY,
                scope VARCHAR(50) NOT NULL,           -- e.g., 'USER', 'GLOBAL', 'MODEL' (maps to LimitScope enum)
                limit_type VARCHAR(50) NOT NULL,      -- e.g., 'COST', 'REQUESTS', 'TOKENS' (maps to LimitType enum)
                max_value DOUBLE PRECISION NOT NULL,  -- Maximum value for the limit
                interval_unit VARCHAR(50) NOT NULL,   -- e.g., 'HOURLY', 'DAILY', 'MONTHLY' (maps to LimitIntervalUnit enum)
                interval_value INTEGER NOT NULL,      -- Numerical value for the interval (e.g., 1 for monthly)
                model_name VARCHAR(255),              -- Specific model this limit applies to (optional)
                username VARCHAR(255),                -- Specific user this limit applies to (optional)
                caller_name VARCHAR(255),             -- Specific caller this limit applies to (optional)
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            # Connection check is already done at the beginning of the method.
            # A cursor is obtained to execute SQL commands.
            # The `with` statement ensures the cursor is closed automatically.
            with self.conn.cursor() as cur:
                for command in commands:
                    cur.execute(command)
                self.conn.commit() # Commit the transaction to make table creations permanent.
            logger.info("Database tables (accounting_entries, api_requests, usage_limits) checked/created successfully.")
        except psycopg2.Error as e:
            logger.error(f"Error during table creation: {e}")
            if self.conn and not self.conn.closed: # Check if connection is still valid before rollback
                self.conn.rollback() # Rollback transaction on any DDL error.
            raise  # Re-raise the psycopg2.Error to allow higher-level handling.
        except Exception as e: # Catch any other unexpected exceptions.
            logger.error(f"An unexpected error occurred during table creation: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise # Re-raise the unexpected exception.

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
        if not self.conn or self.conn.closed:
            logger.error("Cannot insert usage entry, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # SQL INSERT statement for accounting_entries table.
        # Uses %s placeholders for parameters to prevent SQL injection.
        sql = """
            INSERT INTO accounting_entries (
                model_name, prompt_tokens, completion_tokens, total_tokens,
                local_prompt_tokens, local_completion_tokens, local_total_tokens,
                cost, execution_time, timestamp, caller_name, username,
                cached_tokens, reasoning_tokens
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    entry.model, entry.prompt_tokens, entry.completion_tokens, entry.total_tokens,
                    entry.local_prompt_tokens, entry.local_completion_tokens, entry.local_total_tokens,
                    entry.cost, entry.execution_time, entry.timestamp or datetime.now(),
                    entry.caller_name, entry.username, entry.cached_tokens, entry.reasoning_tokens
                ))
                self.conn.commit()
            logger.info(f"Successfully inserted usage entry for user '{entry.username}' and model '{entry.model}'.")
        except psycopg2.Error as e:
            logger.error(f"Error inserting usage entry: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred inserting usage entry: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise

    def insert_api_request(self, request: APIRequest) -> None:
        """
        Inserts an API request record into the api_requests table.

        Args:
            request: An `APIRequest` dataclass object containing the data for the request.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot insert API request, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # SQL INSERT statement for api_requests table.
        sql = """
            INSERT INTO api_requests (
                model_name, username, caller_name, input_tokens, output_tokens, cost, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    request.model, request.username, request.caller_name,
                    request.input_tokens, request.output_tokens, request.cost,
                    request.timestamp or datetime.now()
                ))
                self.conn.commit()
            logger.info(f"Successfully inserted API request for user '{request.username}' and model '{request.model}'.")
        except psycopg2.Error as e:
            logger.error(f"Error inserting API request: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred inserting API request: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
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
        if not self.conn or self.conn.closed:
            logger.error("Cannot insert usage limit, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # SQL INSERT statement for usage_limits table.
        # Enum values are accessed using `.value` for storage as strings.
        sql = """
            INSERT INTO usage_limits (
                scope, limit_type, max_value, interval_unit, interval_value,
                model_name, username, caller_name, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    limit.scope, limit.limit_type, limit.max_value,
                    limit.interval_unit, limit.interval_value,
                    limit.model, limit.username, limit.caller_name,
                    limit.created_at or datetime.now(), limit.updated_at or datetime.now()
                ))
                self.conn.commit()
            logger.info(f"Successfully inserted usage limit for scope '{limit.scope}' and type '{limit.limit_type}'.")
        except psycopg2.Error as e:
            logger.error(f"Error inserting usage limit: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred inserting usage limit: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise

    def delete_usage_limit(self, limit_id: int) -> None:
        """
        Deletes a usage limit entry by its ID from the usage_limits table.

        Args:
            limit_id: The ID of the usage limit to delete.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot delete usage limit, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        sql = "DELETE FROM usage_limits WHERE id = %s;"
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (limit_id,))
                self.conn.commit()
            logger.info(f"Successfully deleted usage limit with ID: {limit_id}.")
        except psycopg2.Error as e:
            logger.error(f"Error deleting usage limit: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred deleting usage limit: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise

    # --- Implemented methods as per subtask ---

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """
        Calculates aggregated usage statistics from `accounting_entries` for a given time period.

        This method computes SUM and AVG for various token counts, cost, and execution time.
        `COALESCE` is used to ensure that 0 or 0.0 is returned for aggregates if no data exists,
        preventing `None` values in the `UsageStats` object.

        Args:
            start: The start `datetime` of the period (inclusive).
            end: The end `datetime` of the period (inclusive).

        Returns:
            A `UsageStats` object containing the aggregated statistics. If no data is found
            for the period, a `UsageStats` object with all values as 0 or 0.0 is returned.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot get period stats, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # SQL query to aggregate usage statistics.
        # COALESCE ensures that if SUM/AVG returns NULL (e.g., no rows), it's replaced with 0 or 0.0.
        query = """
            SELECT
                COALESCE(SUM(prompt_tokens), 0) AS sum_prompt_tokens,
                COALESCE(AVG(prompt_tokens), 0.0) AS avg_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS sum_completion_tokens,
                COALESCE(AVG(completion_tokens), 0.0) AS avg_completion_tokens,
                COALESCE(SUM(total_tokens), 0) AS sum_total_tokens,
                COALESCE(AVG(total_tokens), 0.0) AS avg_total_tokens,
                COALESCE(SUM(local_prompt_tokens), 0) AS sum_local_prompt_tokens,
                COALESCE(AVG(local_prompt_tokens), 0.0) AS avg_local_prompt_tokens,
                COALESCE(SUM(local_completion_tokens), 0) AS sum_local_completion_tokens,
                COALESCE(AVG(local_completion_tokens), 0.0) AS avg_local_completion_tokens,
                COALESCE(SUM(local_total_tokens), 0) AS sum_local_total_tokens,
                COALESCE(AVG(local_total_tokens), 0.0) AS avg_local_total_tokens,
                COALESCE(SUM(cost), 0.0) AS sum_cost,
                COALESCE(AVG(cost), 0.0) AS avg_cost,
                COALESCE(SUM(execution_time), 0.0) AS sum_execution_time,
                COALESCE(AVG(execution_time), 0.0) AS avg_execution_time
            FROM accounting_entries
            WHERE timestamp >= %s AND timestamp <= %s; -- Filters entries within the specified date range.
        """
        try:
            # Uses RealDictCursor to get rows as dictionaries, making it easy to unpack into UsageStats.
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (start, end))
                row = cur.fetchone() # Fetches the single row of aggregated results.
                if row:
                    # Unpack dictionary directly into UsageStats dataclass.
                    return UsageStats(**row)
                else:
                    # This case should ideally not be reached if COALESCE works as expected,
                    # but serves as a fallback to return a default UsageStats object.
                    logger.warning("get_period_stats query returned no row, returning empty UsageStats.")
                    return UsageStats()
        except psycopg2.Error as e:
            logger.error(f"Error getting period stats: {e}")
            raise # Re-raise to allow for higher-level error handling.
        except Exception as e: # Catch any other unexpected exceptions.
            logger.error(f"An unexpected error occurred getting period stats: {e}")
            raise

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        """
        Calculates aggregated usage statistics for each model within a given time period.

        Similar to `get_period_stats` but groups the results by `model_name`.
        `COALESCE` is used for SUM/AVG aggregates to ensure 0 or 0.0 for models with no data,
        or if no data is found for any model.

        Args:
            start: The start `datetime` of the period (inclusive).
            end: The end `datetime` of the period (inclusive).

        Returns:
            A list of tuples, where each tuple contains the model name (str) and
            a `UsageStats` object with its aggregated statistics. Returns an empty list
            if no data is found.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot get model stats, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # SQL query to aggregate usage statistics per model.
        # Groups by model_name and orders by model_name for consistent output.
        query = """
            SELECT
                model_name,
                COALESCE(SUM(prompt_tokens), 0) AS sum_prompt_tokens,
                COALESCE(AVG(prompt_tokens), 0.0) AS avg_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS sum_completion_tokens,
                COALESCE(AVG(completion_tokens), 0.0) AS avg_completion_tokens,
                COALESCE(SUM(total_tokens), 0) AS sum_total_tokens,
                COALESCE(AVG(total_tokens), 0.0) AS avg_total_tokens,
                COALESCE(SUM(local_prompt_tokens), 0) AS sum_local_prompt_tokens,
                COALESCE(AVG(local_prompt_tokens), 0.0) AS avg_local_prompt_tokens,
                COALESCE(SUM(local_completion_tokens), 0) AS sum_local_completion_tokens,
                COALESCE(AVG(local_completion_tokens), 0.0) AS avg_local_completion_tokens,
                COALESCE(SUM(local_total_tokens), 0) AS sum_local_total_tokens,
                COALESCE(AVG(local_total_tokens), 0.0) AS avg_local_total_tokens,
                COALESCE(SUM(cost), 0.0) AS sum_cost,
                COALESCE(AVG(cost), 0.0) AS avg_cost,
                COALESCE(SUM(execution_time), 0.0) AS sum_execution_time,
                COALESCE(AVG(execution_time), 0.0) AS avg_execution_time
            FROM accounting_entries
            WHERE timestamp >= %s AND timestamp <= %s
            GROUP BY model_name -- Aggregates per model.
            ORDER BY model_name; -- Ensures consistent ordering.
        """
        results = []
        try:
            # Uses RealDictCursor for easy conversion to UsageStats.
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (start, end))
                for row_dict in cur:
                    model_name = row_dict.pop('model_name') # Extract model_name for the tuple.
                    # Create UsageStats from the rest of the row dictionary.
                    results.append((model_name, UsageStats(**row_dict)))
            return results
        except psycopg2.Error as e:
            logger.error(f"Error getting model stats: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting model stats: {e}")
            raise

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        """
        Ranks models based on various aggregated metrics (total tokens, cost, etc.)
        within a given time period.

        For each metric, it queries the `accounting_entries` table, groups by `model_name`,
        aggregates the metric, and orders in descending order of the aggregated value.

        Args:
            start: The start `datetime` of the period (inclusive).
            end: The end `datetime` of the period (inclusive).

        Returns:
            A dictionary where keys are metric names (e.g., "total_tokens", "cost")
            and values are lists of tuples. Each tuple contains (model_name, aggregated_value)
            sorted by `aggregated_value` in descending order.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot get model rankings, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # Defines the metrics and their corresponding SQL aggregation functions.
        metrics = {
            "total_tokens": "SUM(total_tokens)",
            "cost": "SUM(cost)",
            "prompt_tokens": "SUM(prompt_tokens)",
            "completion_tokens": "SUM(completion_tokens)",
            "execution_time": "SUM(execution_time)"
        }
        rankings: Dict[str, List[Tuple[str, Any]]] = {metric: [] for metric in metrics}

        try:
            with self.conn.cursor() as cur: # Using standard cursor, as RealDictCursor not strictly needed for tuple output
                for metric_key, agg_func in metrics.items():
                    # model_name is the correct column name in accounting_entries
                    query = f"""
                        SELECT model_name, {agg_func} AS aggregated_value
                        FROM accounting_entries
                        WHERE timestamp >= %s AND timestamp <= %s AND {agg_func} IS NOT NULL -- Exclude entries where the metric is NULL.
                        GROUP BY model_name
                        ORDER BY aggregated_value DESC; -- Rank by the aggregated value.
                    """
                    cur.execute(query, (start, end))
                    rankings[metric_key] = cur.fetchall() # fetchall() returns a list of tuples (model_name, value).
            return rankings
        except psycopg2.Error as e:
            logger.error(f"Error getting model rankings: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting model rankings: {e}")
            raise

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """
        Retrieves the last N usage entries from the `accounting_entries` table,
        ordered by timestamp (most recent first), then by ID for tie-breaking.

        Args:
            n: The number of most recent entries to retrieve. Defaults to 10.

        Returns:
            A list of `UsageEntry` objects. Returns an empty list if no entries are found.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot tail usage entries, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # SQL query to select the last N entries.
        # Ordered by timestamp and then ID (as a secondary sort key for determinism if timestamps are identical).
        query = """
            SELECT * FROM accounting_entries
            ORDER BY timestamp DESC, id DESC
            LIMIT %s;
        """
        entries = []
        try:
            # Uses RealDictCursor for easy mapping to UsageEntry dataclass.
            with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (n,))
                for row_dict in cur:
                    # Map database row (dictionary) to UsageEntry dataclass.
                    # The 'model' field in UsageEntry maps to 'model_name' in the database.
                    entry_data = {
                        'model': row_dict.get('model_name'),
                        'prompt_tokens': row_dict.get('prompt_tokens'),
                        'completion_tokens': row_dict.get('completion_tokens'),
                        'total_tokens': row_dict.get('total_tokens'),
                        'local_prompt_tokens': row_dict.get('local_prompt_tokens'),
                        'local_completion_tokens': row_dict.get('local_completion_tokens'),
                        'local_total_tokens': row_dict.get('local_total_tokens'),
                        'cost': row_dict.get('cost'),
                        'execution_time': row_dict.get('execution_time'),
                        'timestamp': row_dict.get('timestamp'),
                        'caller_name': row_dict.get('caller_name'),
                        'username': row_dict.get('username'),
                        'cached_tokens': row_dict.get('cached_tokens'),
                        'reasoning_tokens': row_dict.get('reasoning_tokens')
                    }
                    # Filter out None values before passing to dataclass constructor
                    # to avoid issues if a field is not Optional in the dataclass
                    # and the DB returns NULL.
                    # However, UsageEntry fields are mostly Optional or have defaults.
                    # Fields in entry_data are directly from the dataclass, so 'model' is used.
                    # The database column is 'model_name', so row_dict.get('model_name') is correct.
                    valid_entry_data = {k: v for k, v in entry_data.items() if v is not None}
                    entries.append(UsageEntry(**valid_entry_data))
            return entries
        except psycopg2.Error as e:
            logger.error(f"Error tailing usage entries: {e}")
            raise
        except Exception as e: # Catch other exceptions, e.g., issues during dataclass instantiation.
            logger.error(f"An unexpected error occurred tailing usage entries: {e}")
            raise

    def purge(self) -> None:
        """
        Deletes all data from `accounting_entries`, `api_requests`, and `usage_limits` tables.

        This is a destructive operation and should be used with caution.
        It iterates through a list of table names and executes a `DELETE FROM` statement for each.
        The operations are performed within a single transaction.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot purge data, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        tables_to_purge = ["accounting_entries", "api_requests", "usage_limits"]
        try:
            with self.conn.cursor() as cur:
                for table in tables_to_purge:
                    # Using f-string for table name is generally safe if table names are controlled internally.
                    # TRUNCATE TABLE could be faster but might have locking implications or issues with foreign keys if they existed.
                    # DELETE FROM is safer in general-purpose code.
                    cur.execute(f"DELETE FROM {table};")
                self.conn.commit() # Commit transaction after all deletes are successful.
            logger.info(f"Successfully purged data from tables: {', '.join(tables_to_purge)}.")
        except psycopg2.Error as e:
            logger.error(f"Error purging data: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback() # Rollback if any delete operation fails.
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred purging data: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
            raise

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
        if not self.conn or self.conn.closed:
            logger.error("Cannot get usage limits, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

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

    def get_api_requests_for_quota(self,
                                   start_time: datetime,
                                   limit_type: LimitType,
                                   model: Optional[str] = None,
                                   username: Optional[str] = None,
                                   caller_name: Optional[str] = None) -> float:
        """
        Aggregates API request data from `api_requests` for quota checking purposes.

        This method calculates a sum or count based on the `limit_type` (e.g., total cost,
        number of requests, total input/output tokens) since a given `start_time`.
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
        if not self.conn or self.conn.closed:
            logger.error("Cannot get API requests for quota, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        # Determine the SQL aggregation function based on the limit_type.
        if limit_type == LimitType.REQUESTS:
            agg_field = "COUNT(*)"
        elif limit_type == LimitType.INPUT_TOKENS:
            agg_field = "COALESCE(SUM(input_tokens), 0)" # Sum of input tokens, 0 if none.
        elif limit_type == LimitType.OUTPUT_TOKENS:
            agg_field = "COALESCE(SUM(output_tokens), 0)" # Sum of output tokens, 0 if none.
        elif limit_type == LimitType.COST:
            agg_field = "COALESCE(SUM(cost), 0.0)" # Sum of costs, 0.0 if none.
        else:
            logger.error(f"Unsupported LimitType for quota aggregation: {limit_type}")
            raise ValueError(f"Unsupported LimitType for quota aggregation: {limit_type}")

        base_query = f"SELECT {agg_field} AS aggregated_value FROM api_requests"
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
            logger.error(f"Error getting API requests for quota (type: {limit_type.value}): {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting API requests for quota (type: {limit_type.value}): {e}")
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
        if not self.conn or self.conn.closed:
            logger.error("Cannot execute query, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

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

        Args:
            user_id: The identifier of the user.
            start_date: Optional start `datetime` for the period (inclusive).
            end_date: Optional end `datetime` for the period (inclusive).

        Returns:
            The total cost as a float. Returns 0.0 if no costs are found for the user
            in the specified period.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        if not self.conn or self.conn.closed:
            logger.error("Cannot get usage costs, database connection is not active.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        query = "SELECT COALESCE(SUM(cost), 0.0) FROM accounting_entries WHERE username = %s"
        # Build query with optional date filters.
        params: List[Any] = [user_id]

        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        query += ";" # Finalize query.

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, tuple(params))
                result = cur.fetchone()
                # Result from SUM will be a single value in a tuple, or None if no rows.
                # COALESCE ensures it's 0.0 if no rows/cost.
                if result and result[0] is not None:
                    return float(result[0])
                return 0.0
        except psycopg2.Error as e:
            logger.error(f"Error getting usage costs for user '{user_id}': {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting usage costs for user '{user_id}': {e}")
            raise

    def set_usage_limit(self, user_id: str, limit_amount: float, limit_type_str: str = "COST") -> None:
        """
        A simplified way to set a usage limit for a user. It creates a `UsageLimit` object
        with `USER` scope and `MONTHLY` interval by default, then calls `insert_usage_limit`.

        This method primarily serves as a convenience. For setting limits with more specific
        scopes, intervals, or other attributes, `insert_usage_limit` should be used directly
        with a fully configured `UsageLimit` object.

        Note: This method attempts an INSERT. If a usage limit that would violate unique
        constraints (e.g. for the same user, scope, type, model, caller) already exists,
        this method will likely raise a `psycopg2.Error` (specifically, an IntegrityError).
        A robust update/insert (upsert) mechanism is not implemented here but would typically
        use `INSERT ... ON CONFLICT DO UPDATE` in PostgreSQL.

        Args:
            user_id: The identifier for the user.
            limit_amount: The maximum value for the limit (e.g., cost amount, token count).
            limit_type_str: String representation of the limit type (e.g., "cost", "requests").
                            Defaults to "cost". Must be a valid `LimitType` enum value.

        Raises:
            ConnectionError: If the database connection is not active.
            ValueError: If `limit_type_str` is not a valid `LimitType`.
            psycopg2.Error: If an error occurs during the underlying `insert_usage_limit` call.
            Exception: For other unexpected errors.
        """
        logger.info(f"Setting usage limit for user '{user_id}', amount {limit_amount}, type '{limit_type_str}'.")
        if not self.conn or self.conn.closed:
            logger.error("Cannot set usage limit, DB connection inactive.")
            raise ConnectionError("Database connection is not active. Call initialize() first.")

        try:
            # Convert the string representation of limit_type to the Enum member.
            limit_type_enum = LimitType(limit_type_str)
        except ValueError: # Raised if limit_type_str is not a valid LimitType value.
            logger.error(f"Invalid limit_type string: {limit_type_str}. Must be one of {LimitType._member_names_}")
            raise ValueError(f"Invalid limit_type string: {limit_type_str}")

        # Create a UsageLimit object with default scope (USER) and interval (MONTHLY).
        usage_limit = UsageLimit(
            scope=LimitScope.USER.value,
            limit_type=limit_type_enum.value,
            max_value=limit_amount,
            interval_unit=TimeInterval.MONTH.value,
            interval_value=1, # Interval value for monthly is 1 (e.g., 1 month).
            username=user_id,
            model=None, # No specific model for this simplified limit.
            caller_name=None, # No specific caller for this simplified limit.
            created_at=datetime.now(), # Set creation timestamp.
            updated_at=datetime.now()  # Set update timestamp.
        )

        try:
            # Call the more general insert_usage_limit method.
            self.insert_usage_limit(usage_limit)
            logger.info(f"Successfully set usage limit for user '{user_id}' via insert_usage_limit call.")
        except psycopg2.Error as db_err:
            logger.error(f"Database error setting usage limit for user '{user_id}': {db_err}")
            raise # Re-raise to allow higher-level handling.
        except Exception as e:
            logger.error(f"Unexpected error setting usage limit for user '{user_id}': {e}")
            raise

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimit]]:
        """
        Retrieves all usage limits defined for a specific user.

        This method is a convenience wrapper around `get_usage_limits`, pre-setting
        the `username` filter.

        Args:
            user_id: The identifier of the user whose limits are to be retrieved.

        Returns:
            A list of `UsageLimit` objects associated with the user, or an empty list
            if no limits are found. Can return `None` if an underlying issue occurs,
            though current implementation of get_usage_limits re-raises errors.

        Raises:
            ConnectionError: If the database connection is not active (from underlying call).
            psycopg2.Error: If an error occurs during SQL execution (from underlying call).
            Exception: For other unexpected errors (from underlying call).
        """
        logger.info(f"Retrieving all usage limits for user_id: {user_id}.")
        try:
            # Delegates to the more generic get_usage_limits method.
            return self.get_usage_limits(username=user_id)
        except Exception as e:
            # Log the error and re-raise. Depending on desired API contract,
            # one might choose to return None or an empty list here.
            logger.error(f"Error retrieving usage limits for user '{user_id}': {e}")
            raise

    def record_api_request(self, request_data: dict) -> None:
        """
        Records an API request from a dictionary of data.

        This method serves as a bridge for systems that might provide request data as a dict.
        It converts the dictionary to an `APIRequest` dataclass object and then calls
        `insert_api_request` for actual database insertion.

        Args:
            request_data: A dictionary containing the API request details.
                          Expected keys should match the fields of the `APIRequest` dataclass
                          (e.g., 'model_name', 'username', 'input_tokens', 'cost').
                          'model_name' is mandatory. 'timestamp' defaults to now if not provided.


        Raises:
            ValueError: If required fields (like 'model_name') are missing from `request_data`
                        or if data conversion fails.
            ConnectionError: If the database connection is not active (from underlying call).
            psycopg2.Error: If an error occurs during SQL execution (from underlying call).
            Exception: For other unexpected errors.
        """
        logger.debug(f"record_api_request(dict) called with data: {request_data}")
        try:
            # Validate that 'model_name' is present and is a string, as it's a non-optional field.
            if not isinstance(request_data.get('model'), str):
                raise ValueError("model (str) is required in request_data.")

            # Construct an APIRequest object from the dictionary.
            # Fields not present in request_data will use their default values if defined in APIRequest.
            api_req = APIRequest(
                model=request_data["model"],
                username=request_data.get("username", ""),  # Default to empty string
                caller_name=request_data.get("caller_name", ""), # Default to empty string
                input_tokens=request_data.get("input_tokens", 0), # Default to 0
                output_tokens=request_data.get("output_tokens", 0), # Default to 0
                cost=request_data.get("cost", 0.0), # Default to 0.0
                timestamp=request_data.get("timestamp", datetime.now())
            )
            self.insert_api_request(api_req)
            logger.info(f"Successfully recorded API request from dict for user '{api_req.username}' model '{api_req.model}'.")
        except KeyError as e:
            logger.error(f"Missing key in request_data for record_api_request: {e}")
            raise ValueError(f"Missing key in request_data: {e}") from e
        except ValueError as ve: # Catch specific ValueErrors from our checks or enum conversions
            logger.error(f"Validation error in record_api_request: {ve}")
            raise
        except Exception as e:
            logger.error(f"Error processing record_api_request with dict: {e}")
            raise
