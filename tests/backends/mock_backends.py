import pytest
from datetime import datetime
from llm_accounting.backends.base import BaseBackend, UsageEntry, UsageStats
from typing import List, Tuple, Dict, Any

class MockBackend(BaseBackend):
    """A mock backend that implements all required methods"""
    def initialize(self) -> None:
        pass

    def insert_usage(self, entry: UsageEntry) -> None:
        pass

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return UsageStats() # Return a default UsageStats object

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        return [] # Return an empty list

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        return {} # Return an empty dictionary

    def purge(self) -> None:
        pass  # pragma: no cover

    def tail(self, n: int = 10) -> List[UsageEntry]:
        return []

    def close(self) -> None:
        pass

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Mock implementation of execute_query"""
        return [{}]  # Return list of empty dicts to match SQLite format

class IncompleteBackend(BaseBackend):
    """A mock backend that doesn't implement all required methods"""
    def initialize(self) -> None:
        pass
