from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from llm_accounting.models.limits import LimitScope, LimitType, UsageLimit
from llm_accounting.models.request import APIRequest


@dataclass
class UsageEntry:
    """Represents a single LLM usage entry"""

    model: Optional[
        str
    ]  # Type matches validation logic but remains required at runtime
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    local_prompt_tokens: Optional[int] = None
    local_completion_tokens: Optional[int] = None
    local_total_tokens: Optional[int] = None
    cost: float = 0.0
    execution_time: float = 0.0
    timestamp: Optional[datetime] = None
    caller_name: str = ""
    username: str = ""
    # Additional token details
    cached_tokens: int = 0
    reasoning_tokens: int = 0

    def __post_init__(self):
        if not self.model or self.model.strip() == "":
            raise ValueError("Model name must be a non-empty string")
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class UsageStats:
    """Represents aggregated usage statistics"""

    sum_prompt_tokens: int = 0
    sum_completion_tokens: int = 0
    sum_total_tokens: int = 0
    sum_local_prompt_tokens: int = 0
    sum_local_completion_tokens: int = 0
    sum_local_total_tokens: int = 0
    sum_cost: float = 0.0
    sum_execution_time: float = 0.0
    avg_prompt_tokens: float = 0.0
    avg_completion_tokens: float = 0.0
    avg_total_tokens: float = 0.0
    avg_local_prompt_tokens: float = 0.0
    avg_local_completion_tokens: float = 0.0
    avg_local_total_tokens: float = 0.0
    avg_cost: float = 0.0
    avg_execution_time: float = 0.0


class BaseBackend(ABC):
    """Base class for all usage tracking backends"""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the backend (create tables, etc.)

        This method should be called before any other operations to ensure the backend
        is properly set up. It's typically called automatically when entering the
        LLMAccounting context.
        """
        pass

    @abstractmethod
    def insert_usage(self, entry: UsageEntry) -> None:
        """Insert a new usage entry"""
        pass

    @abstractmethod
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        pass

    @abstractmethod
    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        """Get statistics grouped by model for a time period"""
        pass

    @abstractmethod
    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, Any]]]:
        """Get model rankings by different metrics"""
        pass

    @abstractmethod
    def purge(self) -> None:
        """Delete all usage entries from the backend"""
        pass

    @abstractmethod
    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close any open connections"""
        pass

    @abstractmethod
    def execute_query(self, query: str) -> list[dict]:
        """Execute a raw SQL SELECT query and return results"""
        pass

    @abstractmethod
    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> List[UsageLimit]:
        """Retrieve usage limits based on specified filters."""
        pass

    @abstractmethod
    def get_api_requests_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> float:
        """
        Retrieve aggregated API request data for quota calculation.
        Returns the sum of the specified limit_type (e.g., input_tokens, cost)
        or the count of requests.
        """
        pass

    @abstractmethod
    def insert_api_request(self, request: APIRequest) -> None:
        """Insert a new API request entry for quota tracking."""
        pass

    @abstractmethod
    def insert_usage_limit(self, limit: UsageLimit) -> None:
        """Insert a new usage limit entry."""
        pass

    @abstractmethod
    def delete_usage_limit(self, limit_id: int) -> None:
        """Delete a usage limit entry by its ID."""
        pass
