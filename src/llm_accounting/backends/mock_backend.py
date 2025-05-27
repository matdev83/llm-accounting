from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import override # Changed import for override

from .base import BaseBackend, UsageEntry, UsageStats, LimitScope, LimitType # LimitScope and LimitType are from base
from ..models.limits import UsageLimitData # Changed from UsageLimit to UsageLimitData


class MockBackend(BaseBackend):
    """
    A mock implementation of the BaseBackend for testing purposes.
    All operations are mocked to emulate positive results without actual database interaction.
    """

    def __init__(self):
        self.entries: List[UsageEntry] = []
        self.limits: List[UsageLimitData] = [] # Changed to store UsageLimitData
        self.next_limit_id: int = 1 # Added for assigning IDs
        self.initialized = False
        self.closed = False

    @override
    def _ensure_connected(self) -> None:
        """Mocks ensuring connection."""
        pass

    @override
    def initialize(self) -> None:
        """Mocks the initialization of the backend."""
        self.initialized = True
        print("MockBackend initialized.")

    @override
    def insert_usage(self, entry: UsageEntry) -> None:
        """Mocks inserting a new usage entry."""
        self.entries.append(entry)
        print(f"MockBackend: Inserted usage for model {entry.model}")

    @override
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Mocks getting aggregated statistics for a time period."""
        print(f"MockBackend: Getting period stats from {start} to {end}")
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

    @override
    def get_model_stats(
        self, start: datetime, end: datetime
    ) -> List[Tuple[str, UsageStats]]:
        """Mocks getting statistics grouped by model for a time period."""
        print(f"MockBackend: Getting model stats from {start} to {end}")
        return [
            ("model_A", UsageStats(sum_total_tokens=1000, sum_cost=10.0)),
            ("model_B", UsageStats(sum_total_tokens=500, sum_cost=5.0)),
        ]

    @override
    def get_model_rankings(
        self, start: datetime, end: datetime
    ) -> Dict[str, List[Tuple[str, Any]]]:
        """Mocks getting model rankings by different metrics."""
        print(f"MockBackend: Getting model rankings from {start} to {end}")
        return {
            "total_tokens": [("model_A", 1000), ("model_B", 500)],
            "cost": [("model_A", 10.0), ("model_B", 5.0)],
        }

    @override
    def purge(self) -> None:
        """Mocks deleting all usage entries."""
        self.entries = []
        self.limits = [] # Also purge limits
        print("MockBackend: All usage entries and limits purged.")

    @override
    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Mocks getting the n most recent usage entries."""
        print(f"MockBackend: Getting last {n} usage entries.")
        if not self.entries:
            # Creating UsageEntry with all required fields if model is not None
            return [
                UsageEntry(
                    model="mock_model_1",
                    prompt_tokens=10,
                    completion_tokens=20,
                    total_tokens=30, # Added for completeness
                    cost=0.01,
                    execution_time=0.05,
                    timestamp=datetime.now() # Added for completeness
                ),
                UsageEntry(
                    model="mock_model_2",
                    prompt_tokens=15,
                    completion_tokens=25,
                    total_tokens=40, # Added for completeness
                    cost=0.02,
                    execution_time=0.08,
                    timestamp=datetime.now() # Added for completeness
                ),
            ][:n]
        return self.entries[-n:]

    @override
    def close(self) -> None:
        """Mocks closing any open connections."""
        self.closed = True
        print("MockBackend closed.")

    @override
    def execute_query(self, query: str) -> list[dict]:
        """Mocks executing a raw SQL SELECT query."""
        print(f"MockBackend: Executing query: {query}")
        if query.strip().upper().startswith("SELECT"):
            return [
                {"id": 1, "model": "mock_model_A", "tokens": 100},
                {"id": 2, "model": "mock_model_B", "tokens": 200},
            ]
        raise ValueError("MockBackend only supports SELECT queries for execute_query.")

    @override
    def insert_usage_limit(self, limit: UsageLimitData) -> None: # Changed type hint to UsageLimitData
        """Mocks inserting a usage limit."""
        # Assign an ID if it's not set (common for new limits)
        if limit.id is None:
            limit.id = self.next_limit_id
            self.next_limit_id += 1
        self.limits.append(limit)
        print(f"MockBackend: Inserted usage limit for scope {limit.scope} with ID {limit.id}")

    @override
    def delete_usage_limit(self, limit_id: int) -> None:
        """Mocks deleting a usage limit."""
        initial_len = len(self.limits)
        self.limits = [limit for limit in self.limits if limit.id != limit_id]
        if len(self.limits) < initial_len:
            print(f"MockBackend: Deleted usage limit with ID {limit_id}")
        else:
            print(f"MockBackend: No usage limit found with ID {limit_id} to delete.")


    @override
    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> List[UsageLimitData]: # Changed return type hint
        """Mocks retrieving usage limits."""
        print(f"MockBackend: Getting usage limits with filters: scope={scope}, model={model}, username={username}, caller_name={caller_name}")
        
        filtered_limits = self.limits
        
        if scope:
            # Assuming scope in UsageLimitData is stored as string, compare with scope.value
            filtered_limits = [limit for limit in filtered_limits if limit.scope == scope.value]
        if model:
            filtered_limits = [limit for limit in filtered_limits if limit.model == model]
        if username:
            filtered_limits = [limit for limit in filtered_limits if limit.username == username]
        if caller_name:
            filtered_limits = [limit for limit in filtered_limits if limit.caller_name == caller_name]
            
        return filtered_limits

    @override
    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> float:
        """
        Mocks getting accounting entries for quota calculation.
        """
        print(f"MockBackend: Getting accounting entries for quota (type: {limit_type.value}) from {start_time} with filters: model={model}, username={username}, caller_name={caller_name}")
        # Simulate some basic filtering for mock purposes
        mock_value = 100.0
        if limit_type == LimitType.REQUESTS:
            mock_value = 10.0 # e.g., 10 requests
        elif limit_type == LimitType.COST:
            mock_value = 5.0 # e.g., $5 cost
        
        # Further refine mock_value based on filters if desired for more complex tests
        if model == "specific_model_for_quota_test":
            mock_value /= 2
        
        return mock_value

    # This method is not part of BaseBackend, but if it exists in MockBackend, it should also be consistent.
    # For this exercise, we assume it's not strictly required to be updated unless specified.
    # If it were to be updated:
    # def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
    #     print(f"MockBackend: Getting usage costs for user {user_id} from {start_date} to {end_date}")
    #     return 50.0
    
    # Ensure all abstract methods from BaseBackend are implemented.
    # If `get_usage_costs` was an abstract method in BaseBackend, it would need @override and consistent types.
    # Currently, it seems like an extra method in MockBackend.

    # Adding a dummy `get_usage_costs` to ensure it exists if other tests rely on it.
    # This specific method was not part of the subtask description to modify for UsageLimitData.
    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        """Mocks getting usage costs for a user."""
        print(f"MockBackend: Getting usage costs for user {user_id} from {start_date} to {end_date}")
        return 50.0 # Dummy value
