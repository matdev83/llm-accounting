import logging
import psycopg2
import psycopg2.extras # For RealDictCursor
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from ..base import UsageEntry, UsageStats
from ...models.limits import UsageLimit, LimitScope, LimitType, TimeInterval

logger = logging.getLogger(__name__)

class QuotaReader:
    def __init__(self, backend_instance):
        self.backend = backend_instance

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
        self.backend._ensure_connected()
        assert self.backend.conn is not None # Pylance: self.conn is guaranteed to be not None here.

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
            with self.backend.conn.cursor() as cur:
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
