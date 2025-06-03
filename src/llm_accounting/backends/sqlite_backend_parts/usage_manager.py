import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import text
from ..base import UsageEntry, UsageStats
from ..sqlite_queries import (get_model_rankings_query, get_model_stats_query,
                             get_period_stats_query, insert_usage_query,
                             tail_query)
from llm_accounting.models.limits import LimitType

logger = logging.getLogger(__name__)

class SQLiteUsageManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def insert_usage(self, entry: UsageEntry) -> None:
        conn = self.connection_manager.get_connection()
        insert_usage_query(conn, entry)
        conn.commit()

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        conn = self.connection_manager.get_connection()
        return get_period_stats_query(conn, start, end)

    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        conn = self.connection_manager.get_connection()
        return get_model_stats_query(conn, start, end)

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        conn = self.connection_manager.get_connection()
        return get_model_rankings_query(conn, start, end)

    def tail(self, n: int = 10) -> List[UsageEntry]:
        conn = self.connection_manager.get_connection()
        return tail_query(conn, n)

    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        end_time: datetime,
        limit_type: LimitType,
        interval_unit: Any, # Add interval_unit parameter
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
    ) -> float:
        conn = self.connection_manager.get_connection()

        if limit_type == LimitType.REQUESTS:
            select_clause = "COUNT(*)"
        elif limit_type == LimitType.INPUT_TOKENS:
            select_clause = "SUM(prompt_tokens)"
        elif limit_type == LimitType.OUTPUT_TOKENS:
            select_clause = "SUM(completion_tokens)"
        elif limit_type == LimitType.COST:
            select_clause = "SUM(cost)"
        else:
            raise ValueError(f"Unknown limit type: {limit_type}")

        # Determine the end_time comparison operator based on whether it's a rolling interval
        end_time_operator = "<"
        # We need to import TimeInterval to use is_rolling()
        from llm_accounting.models.limits import TimeInterval
        if isinstance(interval_unit, TimeInterval) and interval_unit.is_rolling():
            end_time_operator = "<="

        query_base = f"SELECT {select_clause} FROM accounting_entries WHERE timestamp >= :start_time AND timestamp {end_time_operator} :end_time"
        
        # Convert to timezone-naive and format for consistency with SQLite's TIMESTAMP WITHOUT TIME ZONE
        # Use strftime to ensure consistent string format for SQLite comparison
        params_dict: Dict[str, Any] = {
            "start_time": start_time.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.000000'),
            "end_time": end_time.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.000000')
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
        logger.debug(f"Returning final_result: {final_result}")
        return final_result

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        conn = self.connection_manager.get_connection()

        query_base = "SELECT SUM(cost) FROM accounting_entries WHERE username = :user_id"
        params_dict: Dict[str, Any] = {"user_id": user_id}
        conditions = []

        if start_date:
            conditions.append("timestamp >= :start_date")
            params_dict["start_date"] = start_date.strftime('%Y-%m-%d %H:%M:%S.%f')
        if end_date:
            conditions.append("timestamp <= :end_date")
            params_dict["end_date"] = end_date.strftime('%Y-%m-%d %H:%M:%S.%f')

        if conditions:
            query_base += " AND " + " AND ".join(conditions)
        
        result = conn.execute(text(query_base), params_dict)
        scalar_result = result.scalar_one_or_none()
        return float(scalar_result) if scalar_result is not None else 0.0
