import logging
import re
import psycopg2
import psycopg2.extras  # For RealDictCursor
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from ..base import UsageEntry, UsageStats

logger = logging.getLogger(__name__)


class QueryReader:
    def __init__(self, backend_instance):
        self.backend = backend_instance

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
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

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
            WHERE timestamp >= %s AND timestamp <= %s;  -- Filters entries within the specified date range.
        """
        try:
            # Uses RealDictCursor to get rows as dictionaries, making it easy to unpack into UsageStats.
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (start, end))
                row = cur.fetchone()  # Fetches the single row of aggregated results.
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
            raise  # Re-raise to allow for higher-level error handling.
        except Exception as e:  # Catch any other unexpected exceptions.
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
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

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
            GROUP BY model_name  -- Aggregates per model.
            ORDER BY model_name;  -- Ensures consistent ordering.
        """
        results = []
        try:
            # Uses RealDictCursor for easy conversion to UsageStats.
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, (start, end))
                for row_dict in cur:
                    model_name = row_dict.pop('model_name')  # Extract model_name for the tuple.
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
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

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
            with self.backend.conn.cursor() as cur:  # Using standard cursor, as RealDictCursor not strictly needed for tuple output
                for metric_key, agg_func in metrics.items():
                    # model_name is the correct column name in accounting_entries
                    query = f"""
                        SELECT model_name, {agg_func} AS aggregated_value
                        FROM accounting_entries
                        WHERE timestamp >= %s AND timestamp <= %s AND {agg_func} IS NOT NULL  -- Exclude entries where the metric is NULL.
                        GROUP BY model_name
                        ORDER BY aggregated_value DESC;  -- Rank by the aggregated value.
                    """  # nosec B608
                    cur.execute(query, (start, end))
                    rankings[metric_key] = cur.fetchall()  # fetchall() returns a list of tuples (model_name, value).
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
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

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
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
                        'reasoning_tokens': row_dict.get('reasoning_tokens'),
                        'project': row_dict.get('project')
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
        except Exception as e:  # Catch other exceptions, e.g., issues during dataclass instantiation.
            logger.error(f"An unexpected error occurred tailing usage entries: {e}")
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
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

        clean_query = query.strip()
        if ";" in clean_query[:-1]:
            raise ValueError("Semicolons are not allowed in custom queries.")
        if clean_query.endswith(";"):
            clean_query = clean_query[:-1]

        if not clean_query.upper().startswith("SELECT"):
            logger.error(f"Attempted to execute non-SELECT query: {clean_query}")
            raise ValueError("Only SELECT queries are allowed for execution via this method.")
        if re.search(r"\b(ATTACH|ALTER|CREATE|INSERT|UPDATE|DELETE|DROP|REPLACE|GRANT|REVOKE)\b", clean_query, re.IGNORECASE):
            raise ValueError("Only read-only SELECT statements are allowed.")

        results = []
        try:
            # Using RealDictCursor to get results as dictionaries.
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                results = [dict(row) for row in cur.fetchall()]  # Convert RealDictRow objects to standard dicts.
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
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

        query = "SELECT COALESCE(SUM(cost), 0.0) FROM accounting_entries WHERE username = %s"
        # Build query with optional date filters.
        params: List[Any] = [user_id]

        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        query += ";"  # Finalize query.

        try:
            with self.backend.conn.cursor() as cur:
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
