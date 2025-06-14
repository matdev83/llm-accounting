import logging
import psycopg2
import psycopg2.extras  # For RealDictCursor
from typing import Optional, List, Any
from datetime import datetime

from ...models.limits import LimitType

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
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

        agg_field_map = {
            LimitType.REQUESTS: "COUNT(*)",
            LimitType.INPUT_TOKENS: "COALESCE(SUM(prompt_tokens), 0)",
            LimitType.OUTPUT_TOKENS: "COALESCE(SUM(completion_tokens), 0)",
            LimitType.TOTAL_TOKENS: "COALESCE(SUM(total_tokens), 0)",
            LimitType.COST: "COALESCE(SUM(cost), 0.0)",
        }
        agg_field = agg_field_map.get(limit_type)
        if agg_field is None:
            logger.error(f"Unsupported LimitType for quota aggregation: {limit_type}")
            raise ValueError(f"Unsupported LimitType for quota aggregation: {limit_type}")

        base_query = f"SELECT {agg_field} AS aggregated_value FROM accounting_entries"  # nosec B608
        conditions: List[str] = []
        params: List[Any] = []

        # Always filter by start_time.
        conditions.append("timestamp >= %s")
        params.append(start_time)

        filter_map = {
            "model_name": model,
            "username": username,
            "caller_name": caller_name,
        }

        for column, value in filter_map.items():
            if value is not None:
                conditions.append(f"{column} = %s")
                params.append(value)

        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += ";"

        try:
            with self.backend.conn.cursor() as cur:
                cur.execute(query, tuple(params))
                result = cur.fetchone()  # Fetches the single aggregated value.
                return float(result[0]) if result and result[0] is not None else 0.0
        except psycopg2.Error as e:
            logger.error(f"Error getting accounting entries for quota (type: {limit_type.value}): {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting accounting entries for quota (type: {limit_type.value}): {e}")
            raise
