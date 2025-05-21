import logging
from datetime import datetime
from typing import Optional, Type, Dict, List, Tuple

from .backends.base import BaseBackend, UsageEntry, UsageStats
from .backends.sqlite import SQLiteBackend
from .backends.mock_backend import MockBackend # Import MockBackend

logger = logging.getLogger(__name__)

class LLMAccounting:
    """Main interface for LLM usage tracking"""
    
    def __init__(self, backend: Optional[BaseBackend] = None):
        """Initialize with an optional backend. If none provided, uses SQLiteBackend."""
        self.backend = backend or SQLiteBackend()
        
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
            logger.error(f"LLMAccounting context exited with exception: {exc_type.__name__}: {exc_val}")
        
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
        reasoning_tokens: int = 0
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
            reasoning_tokens=reasoning_tokens
        )
        self.backend.insert_usage(entry)
        
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        return self.backend.get_period_stats(start, end)
        
    def get_model_stats(self, start: datetime, end: datetime):
        """Get statistics grouped by model for a time period"""
        return self.backend.get_model_stats(start, end)
        
    def get_model_rankings(self, start_date: datetime, end_date: datetime) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        return self.backend.get_model_rankings(start_date, end_date)

    def purge(self) -> None:
        """Delete all usage entries from the backend"""
        self.backend.purge()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        return self.backend.tail(n)

# Export commonly used classes
__all__ = ['LLMAccounting', 'BaseBackend', 'UsageEntry', 'UsageStats', 'SQLiteBackend', 'MockBackend']
