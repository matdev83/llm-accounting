from datetime import datetime
from typing import Any, Dict, List, Tuple

from .base import BaseBackend, UsageEntry, UsageStats


class MockBackend(BaseBackend):
    """
    A mock implementation of the BaseBackend for testing purposes.
    All operations are mocked to emulate positive results without actual database interaction.
    """

    def __init__(self):
        self.entries: List[UsageEntry] = []
        self.initialized = False
        self.closed = False

    def initialize(self) -> None:
        """Mocks the initialization of the backend."""
        self.initialized = True
        print("MockBackend initialized.")

    def insert_usage(self, entry: UsageEntry) -> None:
        """Mocks inserting a new usage entry."""
        self.entries.append(entry)
        print(f"MockBackend: Inserted usage for model {entry.model}")

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Mocks getting aggregated statistics for a time period."""
        print(f"MockBackend: Getting period stats from {start} to {end}")
        # Return dummy stats
        return UsageStats(
            sum_prompt_tokens=1000,
            sum_completion_tokens=500,
            sum_total_tokens=1500,
            sum_cost=15.0,
            sum_execution_time=1.5,
            avg_prompt_tokens=100.0,
            avg_completion_tokens=50.0,
            avg_total_tokens=150.0,
            avg_cost=1.5,
            avg_execution_time=0.15,
        )

    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        """Mocks getting statistics grouped by model for a time period."""
        print(f"MockBackend: Getting model stats from {start} to {end}")
        # Return dummy model stats
        return [
            ("model_A", UsageStats(sum_total_tokens=1000, sum_cost=10.0)),
            ("model_B", UsageStats(sum_total_tokens=500, sum_cost=5.0)),
        ]

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, Any]]]:
        """Mocks getting model rankings by different metrics."""
        print(f"MockBackend: Getting model rankings from {start} to {end}")
        # Return dummy rankings
        return {
            "total_tokens": [("model_A", 1000), ("model_B", 500)],
            "cost": [("model_A", 10.0), ("model_B", 5.0)],
        }

    def purge(self) -> None:
        """Mocks deleting all usage entries."""
        self.entries = []
        print("MockBackend: All usage entries purged.")

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Mocks getting the n most recent usage entries."""
        print(f"MockBackend: Getting last {n} usage entries.")
        # Return dummy entries or a subset of self.entries
        if not self.entries:
            return [
                UsageEntry(
                    model="mock_model_1",
                    prompt_tokens=10,
                    completion_tokens=20,
                    cost=0.01,
                    execution_time=0.05,
                ),
                UsageEntry(
                    model="mock_model_2",
                    prompt_tokens=15,
                    completion_tokens=25,
                    cost=0.02,
                    execution_time=0.08,
                ),
            ][:n]
        return self.entries[-n:]

    def close(self) -> None:
        """Mocks closing any open connections."""
        self.closed = True
        print("MockBackend closed.")

    def execute_query(self, query: str) -> list[dict]:
        """Mocks executing a raw SQL SELECT query."""
        print(f"MockBackend: Executing query: {query}")
        # Return dummy results for a SELECT query
        if query.strip().upper().startswith("SELECT"):
            return [
                {"id": 1, "model": "mock_model_A", "tokens": 100},
                {"id": 2, "model": "mock_model_B", "tokens": 200},
            ]
        raise ValueError("MockBackend only supports SELECT queries for execute_query.")
