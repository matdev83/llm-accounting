"""Main package initialization for LLM Accounting system.

This package provides core functionality for tracking and managing API usage quotas
and rate limits across multiple services.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .audit_log import AuditLogger
from .backends.base import (
    BaseBackend,
    TransactionalBackend,
    AuditBackend,
    UsageEntry,
    UsageStats,
)
from .backends.mock_backend import MockBackend
from .backends.sqlite import SQLiteBackend
from .models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from .services.quota_service import QuotaService

# Configure a NullHandler for the library's root logger to prevent logs from propagating to the console by default.
# Applications using this library should configure their own logging if they wish to see library logs.
logging.getLogger('llm_accounting').addHandler(logging.NullHandler())

# Initialize logger for the current module after all imports and configurations.
logger = logging.getLogger(__name__)


__all__ = [
    "LLMAccounting",
    "BaseBackend",
    "TransactionalBackend",
    "AuditBackend",
    "UsageEntry",
    "UsageStats",
    "SQLiteBackend",
    "MockBackend",
    "AuditLogger",
    "LimitScope",
    "LimitType",
    "TimeInterval",
    "UsageLimitDTO",
]


class LLMAccounting:
    """Main interface for LLM usage tracking"""

    def __init__(
        self,
        backend: Optional[TransactionalBackend] = None,
        project_name: Optional[str] = None,
        app_name: Optional[str] = None,
        user_name: Optional[str] = None,
        audit_backend: Optional[AuditBackend] = None,
        enforce_project_names: bool = False,
        enforce_user_names: bool = False,
    ):
        """Initialize with optional backends.

        ``backend`` is used for accounting and quota operations. ``audit_backend``
        controls where audit log entries are stored.  If ``audit_backend`` is not
        provided, ``backend`` is used for both.
        """

        self.backend = backend or SQLiteBackend()
        self.audit_backend = audit_backend or self.backend
        self.quota_service = QuotaService(self.backend)
        self.project_name = project_name
        self.app_name = app_name
        self.user_name = user_name
        self.audit_logger = AuditLogger(self.audit_backend)
        self.enforce_project_names = enforce_project_names
        self.enforce_user_names = enforce_user_names

    def _ensure_valid_project(self, project: Optional[str]) -> None:
        if not self.enforce_project_names or project is None:
            return
        valid_projects = set(self.quota_service.list_projects())
        if project not in valid_projects:
            raise ValueError(f"Project name '{project}' is not in allowed projects")

    def _ensure_valid_user(self, user: Optional[str]) -> None:
        if not self.enforce_user_names or user is None:
            return
        valid_users = set(self.quota_service.list_users())
        if user not in valid_users:
            raise ValueError(f"User name '{user}' is not in allowed users")

    def __enter__(self):
        """Initialize the backend when entering context"""
        logger.info("Entering LLMAccounting context.")
        self.backend.initialize()
        if self.audit_backend is not self.backend:
            self.audit_backend.initialize()
        self.audit_backend.initialize_audit_log_schema()
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb):
        """Close the backend when exiting context"""
        logger.info("Exiting LLMAccounting context. Closing backend.")
        self.backend.close()
        if self.audit_backend is not self.backend:
            self.audit_backend.close()
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
        caller_name: Optional[str] = None,  # Changed to Optional[str]
        username: Optional[str] = None,  # Changed to Optional[str]
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        project: Optional[str] = None,
        session: Optional[str] = None,
    ) -> None:
        """Track a new LLM usage entry"""
        self._ensure_valid_project(project if project is not None else self.project_name)
        self._ensure_valid_user(username if username is not None else self.user_name)
        self.backend._ensure_connected()
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
            caller_name=caller_name if caller_name is not None else self.app_name,  # Use instance default
            username=username if username is not None else self.user_name,  # Use instance default
            session=session,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            project=project if project is not None else self.project_name,  # Use instance default
        )
        self.backend.insert_usage(entry)

    def track_usage_with_remaining_limits(
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
        caller_name: Optional[str] = None,
        username: Optional[str] = None,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        project: Optional[str] = None,
        session: Optional[str] = None,
    ) -> List[Tuple[UsageLimitDTO, float]]:
        """Track usage and return remaining quota for applicable limits."""
        self.track_usage(
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
            caller_name=caller_name if caller_name is not None else self.app_name,
            username=username if username is not None else self.user_name,
            session=session,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            project=project if project is not None else self.project_name,
        )

        if total_tokens is None:
            if prompt_tokens is not None and completion_tokens is not None:
                total_tokens = prompt_tokens + completion_tokens
            elif local_prompt_tokens is not None and local_completion_tokens is not None:
                total_tokens = local_prompt_tokens + local_completion_tokens
            else:
                total_tokens = 0

        return self.quota_service.get_remaining_limits(
            model=model,
            username=username if username is not None else self.user_name,
            caller_name=caller_name if caller_name is not None else self.app_name,
            project_name=project if project is not None else self.project_name,
            input_tokens=prompt_tokens or local_prompt_tokens or 0,
            completion_tokens=completion_tokens or local_completion_tokens or 0,
            cost=cost,
        )


    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        self.backend._ensure_connected()
        return self.backend.get_period_stats(start, end)

    def get_model_stats(self, start: datetime, end: datetime):
        """Get statistics grouped by model for a time period"""
        self.backend._ensure_connected()
        return self.backend.get_model_stats(start, end)

    def get_model_rankings(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        self.backend._ensure_connected()
        return self.backend.get_model_rankings(start_date, end_date)

    def purge(self) -> None:
        """Delete all usage entries from the backend"""
        self.backend._ensure_connected()
        self.backend.purge()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        self.backend._ensure_connected()
        return self.backend.tail(n)

    def check_quota(
        self,
        model: str,
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float = 0.0,
        project_name: Optional[str] = None,
        completion_tokens: int = 0,
        session: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check if the current request exceeds any defined quotas."""
        self._ensure_valid_project(project_name)
        self._ensure_valid_user(username)
        self.backend._ensure_connected()
        return self.quota_service.check_quota(
            model=model,
            username=username,
            caller_name=caller_name,
            input_tokens=input_tokens,
            cost=cost,
            project_name=project_name,
            completion_tokens=completion_tokens,
            session=session,
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
        project_name: Optional[str] = None,
    ) -> None:
        """Sets a new usage limit."""
        self._ensure_valid_project(project_name)
        self._ensure_valid_user(username)
        self.backend._ensure_connected()
        limit = UsageLimitDTO(
            scope=scope.value if isinstance(scope, LimitScope) else scope,
            limit_type=limit_type.value if isinstance(limit_type, LimitType) else limit_type,
            max_value=max_value,
            interval_unit=interval_unit.value if isinstance(interval_unit, TimeInterval) else interval_unit,
            interval_value=interval_value,
            model=model,
            username=username,
            caller_name=caller_name,
            project_name=project_name,
        )
        self.quota_service.insert_limit(limit)

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> List[UsageLimitDTO]:
        """Retrieves configured usage limits."""
        self.backend._ensure_connected()
        return self.backend.get_usage_limits(
            scope=scope,
            model=model,
            username=username,
            caller_name=caller_name,
            project_name=project_name
        )

    def delete_usage_limit(self, limit_id: int) -> None:
        """Deletes a usage limit by its ID."""
        self.backend._ensure_connected()
        self.quota_service.delete_limit(limit_id)

    def get_db_path(self) -> Optional[str]:
        """
        Returns the database path if the backend is a SQLiteBackend.
        Otherwise, returns None.
        """
        if isinstance(self.backend, SQLiteBackend):
            return self.backend.db_path
        return None
