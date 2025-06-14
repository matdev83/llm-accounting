import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
import psycopg2  # For error handling
import psycopg2.extras  # For RealDictCursor

from ..base import UsageEntry, UsageStats, AuditLogEntry  # Added AuditLogEntry
from ...models.limits import UsageLimitDTO, LimitScope, LimitType

from .query_reader import QueryReader
from .limit_manager import LimitManager
from .quota_reader import QuotaReader

logger = logging.getLogger(__name__)


class QueryExecutor:
    def __init__(self, backend_instance):
        self.backend = backend_instance
        self._query_reader = QueryReader(backend_instance)
        self._quota_reader = QuotaReader(backend_instance)
        # Assuming backend_instance has a data_inserter attribute
        self._limit_manager = LimitManager(backend_instance, backend_instance.data_inserter)

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return self._query_reader.get_period_stats(start, end)

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        return self._query_reader.get_model_stats(start, end)

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        return self._query_reader.get_model_rankings(start, end)

    def tail(self, n: int = 10) -> List[UsageEntry]:
        return self._query_reader.tail(n)

    def get_usage_limits(self,
                         scope: Optional[LimitScope] = None,
                         model: Optional[str] = None,
                         username: Optional[str] = None,
                         caller_name: Optional[str] = None) -> List[UsageLimitDTO]:
        return self._limit_manager.get_usage_limits(scope, model, username, caller_name)

    def get_accounting_entries_for_quota(self,
                                         start_time: datetime,
                                         limit_type: LimitType,
                                         model: Optional[str] = None,
                                         username: Optional[str] = None,
                                         caller_name: Optional[str] = None) -> float:
        return self._quota_reader.get_accounting_entries_for_quota(start_time, limit_type, model, username, caller_name)

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        return self._query_reader.execute_query(query)

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        return self._query_reader.get_usage_costs(user_id, start_date, end_date)

    def set_usage_limit(self, user_id: str, limit_amount: float, limit_type_str: str = "COST") -> None:
        self._limit_manager.set_usage_limit(user_id, limit_amount, limit_type_str)

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimitDTO]]:
        return self._limit_manager.get_usage_limit(user_id)

    def get_audit_log_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        app_name: Optional[str] = None,
        user_name: Optional[str] = None,
        project: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AuditLogEntry]:
        """
        Retrieves audit log entries based on specified filter criteria.
        The connection is managed by the calling PostgreSQLBackend method.
        """
        # self.backend._ensure_connected() is assumed to be called by PostgreSQLBackend
        assert self.backend.conn is not None, "Database connection is not established."

        query_parts = ["SELECT id, timestamp, app_name, user_name, model, prompt_text, response_text, remote_completion_id, project, log_type FROM audit_log_entries"]
        conditions = []
        params: List[Any] = []

        if start_date:
            conditions.append("timestamp >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= %s")
            params.append(end_date)
        if app_name:
            conditions.append("app_name = %s")
            params.append(app_name)
        if user_name:
            conditions.append("user_name = %s")
            params.append(user_name)
        if project:
            conditions.append("project = %s")
            params.append(project)
        if log_type:
            conditions.append("log_type = %s")
            params.append(log_type)

        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))

        query_parts.append("ORDER BY timestamp DESC")  # Default ordering

        if limit is not None:
            query_parts.append("LIMIT %s")
            params.append(limit)

        final_query = " ".join(query_parts)

        results = []
        try:
            # The cursor will be managed (opened and closed) by the 'with' statement.
            # RealDictCursor allows accessing columns by name.
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(final_query, tuple(params))
                rows = cur.fetchall()
                for row_dict in rows:
                    results.append(
                        AuditLogEntry(
                            id=row_dict["id"],
                            timestamp=row_dict["timestamp"],  # TIMESTAMPTZ from DB -> timezone-aware datetime
                            app_name=row_dict["app_name"],
                            user_name=row_dict["user_name"],
                            model=row_dict["model"],
                            prompt_text=row_dict["prompt_text"],
                            response_text=row_dict["response_text"],
                            remote_completion_id=row_dict["remote_completion_id"],
                            project=row_dict["project"],
                            log_type=row_dict["log_type"],
                        )
                    )
            logger.info(f"Successfully retrieved {len(results)} audit log entries.")
        except psycopg2.Error as e:
            logger.error(f"Error retrieving audit log entries: {e}")
            # Re-raise to allow PostgreSQLBackend to handle transaction control (though this is a read operation)
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred retrieving audit log entries: {e}")
            raise

        return results
