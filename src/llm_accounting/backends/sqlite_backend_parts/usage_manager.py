import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import text
from sqlalchemy.engine import Connection  # Import Connection for type hinting
from ..base import UsageEntry, UsageStats
from ..sqlite_queries import (get_model_rankings_query, get_model_stats_query,
                              get_period_stats_query, insert_usage_query,
                              tail_query)
from llm_accounting.models.limits import LimitType

logger = logging.getLogger(__name__)

# Removed first definition of SQLiteUsageManager and redundant Connection import


class SQLiteUsageManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def insert_usage(self, conn: Connection, entry: UsageEntry) -> None:
        insert_usage_query(conn, entry)
        # conn.commit() # Let the caller handle commit

    def get_period_stats(self, conn: Connection, start: datetime, end: datetime) -> UsageStats:
        return get_period_stats_query(conn, start, end)

    def get_model_stats(
        self, conn: Connection, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        return get_model_stats_query(conn, start, end)

    def get_model_rankings(
        self, conn: Connection, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        return get_model_rankings_query(conn, start, end)

    def tail(self, conn: Connection, n: int = 10) -> List[UsageEntry]:
        return tail_query(conn, n)

    def get_accounting_entries_for_quota(
        self,
        conn: Connection,
        start_time: datetime,
        end_time: datetime,
        limit_type: LimitType,
        interval_unit: Any,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
    ) -> float:
        if limit_type == LimitType.REQUESTS:
            select_clause = "COUNT(*)"
        elif limit_type == LimitType.INPUT_TOKENS:
            select_clause = "SUM(prompt_tokens)"
        elif limit_type == LimitType.OUTPUT_TOKENS:
            select_clause = "SUM(completion_tokens)"
        elif limit_type == LimitType.TOTAL_TOKENS:
            select_clause = "SUM(total_tokens)"
        elif limit_type == LimitType.COST:
            select_clause = "SUM(cost)"
        else:
            raise ValueError(f"Unknown limit type: {limit_type}")

        end_time_operator = "<="

        query_base = f"SELECT {select_clause} FROM accounting_entries WHERE timestamp >= :start_time AND timestamp {end_time_operator} :end_time"  # nosec B608

        params_dict: Dict[str, Any] = {
            "start_time": start_time.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.%f'),
            "end_time": end_time.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.%f')
        }
        conditions = []

        if model:
            conditions.append("model = :model")
            params_dict["model"] = model
        if username:
            conditions.append("username = :username")
            params_dict["username"] = username
        if caller_name:
            conditions.append("caller_name = :caller_name")
            params_dict["caller_name"] = caller_name

        if project_name is not None:
            conditions.append("project = :project_name")
            params_dict["project_name"] = project_name
        elif filter_project_null is True:
            conditions.append("project IS NULL")
        elif filter_project_null is False:
            conditions.append("project IS NOT NULL")

        if conditions:
            query_base += " AND " + " AND ".join(conditions)

        logger.debug(f"Executing SQL query: {query_base}")
        logger.debug(f"With parameters: {params_dict}")

        result = conn.execute(text(query_base), params_dict)
        scalar_result = result.scalar_one_or_none()

        logger.debug(f"Raw scalar result from DB: {scalar_result}")

        final_result = float(scalar_result) if scalar_result is not None else 0.0
        logger.debug(f"Returning final_result: {final_result} for limit_type: {limit_type.value}, model: {model}, username: {username}, caller: {caller_name}, project: {project_name}")
        return final_result

    def get_usage_costs(self, conn: Connection, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        query_base = "SELECT SUM(cost) FROM accounting_entries WHERE username = :user_id"
        params_dict: Dict[str, Any] = {"user_id": user_id}
        conditions = []

        if start_date:
            conditions.append("timestamp >= :start_date")
            params_dict["start_date"] = start_date.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.%f')
        if end_date:
            conditions.append("timestamp <= :end_date")
            params_dict["end_date"] = end_date.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.%f')

        if conditions:
            query_base += " AND " + " AND ".join(conditions)

        result = conn.execute(text(query_base), params_dict)
        scalar_result = result.scalar_one_or_none()
        return float(scalar_result) if scalar_result is not None else 0.0
