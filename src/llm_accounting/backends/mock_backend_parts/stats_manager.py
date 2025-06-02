import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from ..base import UsageStats


class MockStatsManager:
    def __init__(self, parent_backend):
        self.parent_backend = parent_backend

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Mocks getting aggregated statistics for a time period."""
        logging.debug(f"MockBackend: Getting period stats from {start} to {end}")
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
        logging.debug(f"MockBackend: Getting model stats from {start} to {end}")
        return [
            ("model_A", UsageStats(sum_total_tokens=1000, sum_cost=10.0)),
            ("model_B", UsageStats(sum_total_tokens=500, sum_cost=5.0)),
        ]

    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, Any]]]:
        """Mocks getting model rankings by different metrics."""
        logging.debug(f"MockBackend: Getting model rankings from {start} to {end}")
        return {
            "total_tokens": [("model_A", 1000), ("model_B", 500)],
            "cost": [("model_A", 10.0), ("model_B", 5.0)],
        }

    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        """Mocks getting usage costs for a user."""
        logging.debug(f"MockBackend: Getting usage costs for user {user_id} from {start_date} to {end_date}")
        return 50.0
