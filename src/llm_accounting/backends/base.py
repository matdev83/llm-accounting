from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

@dataclass
class UsageEntry:
    """Represents a single LLM usage entry"""
    model: Optional[str]  # Type matches validation logic but remains required at runtime
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
    
    def _validate_db_path(self, db_path: str) -> None:
        """Validate the database path is accessible and has correct extension"""
        import os
        import pathlib
        
        # Check file extension
        if not db_path.lower().endswith(('.db', '.sqlite')):
            raise ValueError(f"Invalid database file extension: {db_path}")
            
        # Check path accessibility
        try:
            path = pathlib.Path(db_path)
            if path.is_absolute() and path.drive == 'C:' and path.parts[1].lower() in ('windows', 'program files'):
                raise PermissionError(f"Access denied: {db_path} is in protected system directory")
            if not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(f"Invalid database path: {db_path}") from e
    
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
    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        """Get statistics grouped by model for a time period"""
        pass

    @abstractmethod
    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
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
