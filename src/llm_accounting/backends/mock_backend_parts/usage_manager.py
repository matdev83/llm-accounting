import logging
from datetime import datetime
from typing import List

from ..base import UsageEntry


class MockUsageManager:
    def __init__(self, parent_backend):
        self.parent_backend = parent_backend

    def insert_usage(self, entry: UsageEntry) -> None:
        """Mocks inserting a new usage entry."""
        self.parent_backend.entries.append(entry)
        logging.debug(f"MockBackend: Inserted usage for model {entry.model}")  # noqa: T201

    def purge(self) -> None:
        """Mocks deleting all usage entries."""
        self.parent_backend.entries = []
        self.parent_backend.limits = []
        logging.debug("MockBackend: All usage entries and limits purged.")  # noqa: T201

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Mocks getting the n most recent usage entries."""
        logging.debug(f"MockBackend: Getting last {n} usage entries.")  # noqa: T201
        if not self.parent_backend.entries:
            return [
                UsageEntry(
                    model="mock_model_1",
                    prompt_tokens=10,
                    completion_tokens=20,
                    total_tokens=30,
                    cost=0.01,
                    execution_time=0.05,
                    timestamp=datetime.now()
                ),
                UsageEntry(
                    model="mock_model_2",
                    prompt_tokens=15,
                    completion_tokens=25,
                    total_tokens=40,
                    cost=0.02,
                    execution_time=0.08,
                    timestamp=datetime.now()
                ),
            ][:n]
        return self.parent_backend.entries[-n:]
