from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models.limits import LimitScope, LimitType, UsageLimitDTO


@dataclass
class AuditLogEntry:
    """Represents a single audit log entry"""

    id: Optional[int]  # typically assigned by the database
    timestamp: datetime
    app_name: str
    user_name: str
    model: str
    prompt_text: Optional[str]
    response_text: Optional[str]
    remote_completion_id: Optional[str]
    project: Optional[str]
    log_type: str  # e.g., 'prompt', 'response', 'event'
    session: Optional[str] = None

    def __post_init__(self):
        # Ensure timestamp is set, similar to UsageEntry, though it's not Optional here.
        # This is more of a placeholder if we decide to add default logic later.
        if self.timestamp is None:
            # This case should ideally not be hit if timestamp is always provided.
            # from datetime import timezone  # Import here if not at top level
            # self.timestamp = datetime.now(timezone.utc)
            pass  # Keep as is, timestamp is non-optional


@dataclass
class UsageEntry:
    """Represents a single LLM usage entry"""

    model: str  # Changed to non-optional, __post_init__ handles validation
    # id will be added by CSVBackend, other backends handle it via DB
    id: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    local_prompt_tokens: Optional[int] = None
    local_completion_tokens: Optional[int] = None
    local_total_tokens: Optional[int] = None
    cost: float = 0.0
    execution_time: float = 0.0
    timestamp: Optional[datetime] = None
    caller_name: Optional[str] = None
    username: Optional[str] = None
    project: Optional[str] = None
    session: Optional[str] = None
    # Additional token details
    cached_tokens: Optional[int] = 0  # Keep Optional for flexibility if not always provided
    reasoning_tokens: Optional[int] = 0  # Keep Optional

    def __post_init__(self):
        if not hasattr(self, 'model') or not self.model or self.model.strip() == "":
            raise ValueError("Model name must be a non-empty string")
        if not hasattr(self, 'timestamp') or self.timestamp is None:  # Ensure timestamp exists
            self.timestamp = datetime.now()
        # Ensure numeric fields that default to None but are summed are 0 if None for safety,
        # though CSVBackend already handles None to 0 conversion.
        # This is more for direct DTO usage if that occurs.
        token_fields = [
            "prompt_tokens", "completion_tokens", "total_tokens",
            "local_prompt_tokens", "local_completion_tokens", "local_total_tokens",
            "cached_tokens", "reasoning_tokens"
        ]
        for field_name in token_fields:
            if getattr(self, field_name) is None:
                setattr(self, field_name, 0)

        if self.cost is None:
            self.cost = 0.0
        if self.execution_time is None:
            self.execution_time = 0.0


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


@dataclass
class UserRecord:
    user_name: str
    ou_name: Optional[str] = None
    email: Optional[str] = None
    enabled: bool = True
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    last_enabled_at: Optional[datetime] = None
    last_disabled_at: Optional[datetime] = None


class TransactionalBackend(ABC):
    """Interface for transactional database operations."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the backend (create tables, etc.)"""
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
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
        filter_username_null: Optional[bool] = None,
        filter_caller_name_null: Optional[bool] = None,
    ) -> List[UsageLimitDTO]:
        """Retrieve usage limits based on specified filters."""
        pass

    @abstractmethod
    def get_accounting_entries_for_quota(
        self,
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
        """Retrieve aggregated API request data for quota calculation."""
        pass

    @abstractmethod
    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """Insert a new usage limit entry."""
        pass

    @abstractmethod
    def delete_usage_limit(self, limit_id: int) -> None:
        """Delete a usage limit entry by its ID."""
        pass

    @abstractmethod
    def _ensure_connected(self) -> None:
        """Ensure the backend has an active connection."""
        pass

    @abstractmethod
    def get_usage_costs(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> float:
        """Retrieve aggregated usage costs for a user."""
        pass

    # --- Project Management ---

    @abstractmethod
    def create_project(self, name: str) -> None:
        """Create a new allowed project name."""
        pass

    @abstractmethod
    def list_projects(self) -> List[str]:
        """Return the list of allowed project names."""
        pass

    @abstractmethod
    def update_project(self, name: str, new_name: str) -> None:
        """Rename an existing project."""
        pass

    @abstractmethod
    def delete_project(self, name: str) -> None:
        """Delete a project from the dictionary."""
        pass

    # --- User Management ---

    @abstractmethod
    def create_user(
        self,
        user_name: str,
        ou_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        """Create a new allowed user."""
        pass

    @abstractmethod
    def list_users(self) -> List[UserRecord]:
        """Return the list of allowed users."""
        pass

    @abstractmethod
    def update_user(
        self,
        user_name: str,
        new_user_name: Optional[str] = None,
        ou_name: Optional[str] = None,
        email: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Update fields of an existing user."""
        pass

    @abstractmethod
    def set_user_enabled(self, user_name: str, enabled: bool) -> None:
        """Enable or disable a user."""
        pass


class AuditBackend(ABC):
    """Interface for non-transactional (audit logging) operations."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the backend if required."""
        pass

    @abstractmethod
    def initialize_audit_log_schema(self) -> None:
        """Ensure the audit log schema is initialized."""
        pass

    @abstractmethod
    def log_audit_event(self, entry: AuditLogEntry) -> None:
        """Insert a new audit log entry."""
        pass

    @abstractmethod
    def log_quota_rejection(self, session: str, rejection_message: str, created_at: Optional[datetime] = None) -> None:
        """Store information about a rejected quota check."""
        pass

    @abstractmethod
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
        """Retrieve audit log entries based on filter criteria."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close any resources held by the backend."""
        pass


class BaseBackend(TransactionalBackend, AuditBackend, ABC):
    """Combined interface supporting both transactional and audit operations."""

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
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
        filter_username_null: Optional[bool] = None,
        filter_caller_name_null: Optional[bool] = None,
    ) -> List[UsageLimitDTO]:
        """Retrieve usage limits based on specified filters."""
        pass

    @abstractmethod
    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        end_time: datetime,
        limit_type: LimitType,
        interval_unit: Any,  # Use Any for now to avoid circular import with TimeInterval
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
    ) -> float:
        """
        Retrieve aggregated API request data for quota calculation.
        Returns the sum of the specified limit_type (e.g., input_tokens, cost)
        or the count of requests.
        """
        pass

    @abstractmethod
    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """Insert a new usage limit entry."""
        pass

    @abstractmethod
    def delete_usage_limit(self, limit_id: int) -> None:
        """Delete a usage limit entry by its ID."""
        pass

    @abstractmethod
    def _ensure_connected(self) -> None:
        """
        Ensures the backend has an active connection.
        Implementations should handle connection establishment or re-establishment.
        This method should be idempotent.
        """
        pass

    @abstractmethod
    def initialize_audit_log_schema(self) -> None:
        """Ensure the audit log schema (e.g., tables) is initialized."""
        pass

    @abstractmethod
    def log_audit_event(self, entry: AuditLogEntry) -> None:
        """Insert a new audit log entry."""
        pass

    @abstractmethod
    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        """Retrieve aggregated usage costs for a user."""
        pass

    @abstractmethod
    def log_quota_rejection(self, session: str, rejection_message: str, created_at: Optional[datetime] = None) -> None:
        """Store information about a rejected quota check."""
        pass

    @abstractmethod
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
        """Retrieve audit log entries based on filter criteria."""
        pass

    # --- Project Management ---

    @abstractmethod
    def create_project(self, name: str) -> None:
        """Create a new allowed project name."""
        pass

    @abstractmethod
    def list_projects(self) -> List[str]:
        """Return the list of allowed project names."""
        pass

    @abstractmethod
    def update_project(self, name: str, new_name: str) -> None:
        """Rename an existing project."""
        pass

    @abstractmethod
    def delete_project(self, name: str) -> None:
        """Delete a project from the dictionary."""
        pass

    # --- User Management ---

    @abstractmethod
    def create_user(
        self,
        user_name: str,
        ou_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> None:
        """Create a new allowed user."""
        pass

    @abstractmethod
    def list_users(self) -> List[UserRecord]:
        """Return the list of allowed users."""
        pass

    @abstractmethod
    def update_user(
        self,
        user_name: str,
        new_user_name: Optional[str] = None,
        ou_name: Optional[str] = None,
        email: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Update fields of an existing user."""
        pass

    @abstractmethod
    def set_user_enabled(self, user_name: str, enabled: bool) -> None:
        """Enable or disable a user."""
        pass
