import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from ..base import UsageEntry, UsageStats
from ...models.limits import UsageLimit, UsageLimitDTO, LimitScope, LimitType, TimeInterval

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
