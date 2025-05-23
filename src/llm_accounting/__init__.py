"""Main package initialization for LLM Accounting system.

This package provides core functionality for tracking and managing API usage quotas
and rate limits across multiple services.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .backends.base import BaseBackend, UsageEntry, UsageStats
from .backends.mock_backend import MockBackend
from .backends.sqlite import SQLiteBackend
from .models.limits import LimitScope, LimitType, TimeInterval, UsageLimit
"""Main package initialization for LLM Accounting system.

This package provides core functionality for tracking and managing API usage quotas
and rate limits across multiple services.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .backends.base import BaseBackend, UsageEntry, UsageStats
from .backends.mock_backend import MockBackend
from .backends.sqlite import SQLiteBackend
from .models.limits import LimitScope, LimitType, TimeInterval, UsageLimit
from .services.quota_service import QuotaService
from .audit_log import AuditLogger

logger = logging.getLogger(__name__)


class LLMAccounting:
    """Main interface for LLM usage tracking"""

    def __init__(self, backend: Optional[BaseBackend] = None):
        """Initialize with an optional backend. If none provided, uses SQLiteBackend."""
        self.backend = backend or SQLiteBackend()
        self.quota_service = QuotaService(self.backend)

    def __enter__(self):
        """Initialize the backend when entering context"""
        logger.info("Entering LLMAccounting context.")
        self.backend.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the backend when exiting context"""
        logger.info("Exiting LLMAccounting context. Closing backend.")
        self.backend.close()
        if exc_type:
            logger.error(
                f"LLMAccounting context exited with exception: {exc_type.__name__}: {exc_val}"
            )

    def track_usage(
        self,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        local_prompt_tokens: Optional[int] = None,
        local_completion_tokens: Optional[int] = None,
        local_total_tokens: Optional[int] = None,
        cost: float = 0.0,
        execution_time: float = 0.0,
        timestamp: Optional[datetime] = None,
        caller_name: str = "",
        username: str = "",
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> None:
        """Track a new LLM usage entry"""
        entry = UsageEntry(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            local_prompt_tokens=local_prompt_tokens,
            local_completion_tokens=local_completion_tokens,
            local_total_tokens=local_total_tokens,
            cost=cost,
            execution_time=execution_time,
            timestamp=timestamp,
            caller_name=caller_name,
            username=username,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )
        self.backend.insert_usage(entry)

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        return self.backend.get_period_stats(start, end)

    def get_model_stats(self, start: datetime, end: datetime):
        """Get statistics grouped by model for a time period"""
        return self.backend.get_model_stats(start, end)

    def get_model_rankings(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        return self.backend.get_model_rankings(start_date, end_date)

    def purge(self) -> None:
        """Delete all usage entries from the backend"""
        self.backend.purge()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        return self.backend.tail(n)

    def check_quota(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float = 0.0,
    ) -> Tuple[bool, Optional[str]]:
        """Check if the current request exceeds any defined quotas."""
        return self.quota_service.check_quota(
            model, username, caller_name, input_tokens, cost
        )

    def set_usage_limit(
        self,
        scope: LimitScope,
        limit_type: LimitType,
        max_value: float,
        interval_unit: TimeInterval,
        interval_value: int,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> None:
        """Sets a new usage limit."""
        limit = UsageLimit(
            scope=scope.value,
            limit_type=limit_type.value,
            max_value=max_value,
            interval_unit=interval_unit.value,
            interval_value=interval_value,
            model=model,
            username=username,
            caller_name=caller_name,
        )
        self.backend.insert_usage_limit(limit)

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> List[UsageLimit]:
        """Retrieves configured usage limits."""
        return self.backend.get_usage_limits(scope, model, username, caller_name)

    def delete_usage_limit(self, limit_id: int) -> None:
        """Deletes a usage limit by its ID."""
        self.backend.delete_usage_limit(limit_id)

    def get_db_path(self) -> Optional[str]:
        """
        Returns the database path if the backend is a SQLiteBackend.
        Otherwise, returns None.
        """
        if isinstance(self.backend, SQLiteBackend):
            return self.backend.db_path
        return None


# Export commonly used classes
__all__ = [
    "LLMAccounting",
    "BaseBackend",
    "UsageEntry",
    "UsageStats",
    "SQLiteBackend",
    "MockBackend",
    "AuditLogger",
    "LimitScope",
    "LimitType",
    "TimeInterval",
    "UsageLimit",
]
