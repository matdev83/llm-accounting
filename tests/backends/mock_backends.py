from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


from llm_accounting.backends.base import BaseBackend, UsageEntry, UsageStats
from llm_accounting.models.limits import LimitScope, LimitType, UsageLimit
from llm_accounting.models.request import APIRequest


class MockBackend(BaseBackend):
    """A mock backend that implements all required methods"""

    def initialize(self) -> None:
        pass

    def insert_usage(self, entry: UsageEntry) -> None:
        pass

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return UsageStats()  # Return a default UsageStats object

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        return []  # Return an empty list

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        return {}  # Return an empty dictionary

    def purge(self) -> None:
        pass  # pragma: no cover

    def tail(self, n: int = 10) -> List[UsageEntry]:
        return []

    def close(self) -> None:
        pass

    def add_limit(self, limit: UsageLimit) -> UsageLimit:
        # In a mock, we can just return the limit itself, or a modified version
        # if we want to simulate ID assignment or timestamp updates.
        # For simplicity, we'll just return the input limit for now.
        return limit

    def get_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None
    ) -> List[UsageLimit]:
        return []

    def delete_limit(self, limit_id: int) -> None:
        pass

    def get_api_requests_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None
    ) -> float:
        return 0.0

    def insert_api_request(self, request: APIRequest) -> None:
        pass


class IncompleteBackend(BaseBackend):
    """A mock backend that doesn't implement all required methods"""

    def initialize(self) -> None:
        pass
