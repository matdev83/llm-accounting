from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from typing_extensions import override # Changed import for override


from llm_accounting.backends.base import BaseBackend, UsageEntry, UsageStats
# Changed UsageLimit to UsageLimitData and ensure other enums are available if needed by this file
from llm_accounting.models.limits import LimitScope, LimitType, UsageLimitData


class MockBackend(BaseBackend):
    """A mock backend that implements all required methods for BaseBackend interface testing."""

    @override
    def _ensure_connected(self) -> None:
        """Mocks ensuring connection."""
        pass

    @override
    def initialize(self) -> None:
        pass

    @override
    def insert_usage(self, entry: UsageEntry) -> None:
        pass

    @override
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        return UsageStats()  # Return a default UsageStats object

    @override
    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        return []  # Return an empty list

    @override
    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        return {}  # Return an empty dictionary

    @override
    def purge(self) -> None:
        pass

    @override
    def tail(self, n: int = 10) -> List[UsageEntry]:
        return []

    @override
    def close(self) -> None:
        pass

    @override
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Mock implementation of execute_query"""
        # Simulate a SELECT query behavior; actual results don't matter for interface testing
        if query.strip().upper().startswith("SELECT"):
            return [{}] 
        raise ValueError("MockBackend in test_base.py only supports SELECT for execute_query.")


    @override
    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None
    ) -> List[UsageLimitData]: # Changed return type to List[UsageLimitData]
        return []

    @override
    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None
    ) -> float:
        return 0.0

    @override
    def insert_usage_limit(self, limit: UsageLimitData) -> None: # Changed argument type to UsageLimitData
        pass

    @override
    def delete_usage_limit(self, limit_id: int) -> None:
        pass


class IncompleteBackend(BaseBackend):
    """A mock backend that doesn't implement all required methods for BaseBackend interface testing."""

    # Missing several abstract methods from BaseBackend

    def initialize(self) -> None:
        pass

    # For example, if insert_usage was missing, TypeError would be raised by abc.
    # def insert_usage(self, entry: UsageEntry) -> None:
    #     pass
    
    # To make it truly incomplete for testing purposes, we'd comment out some abstract methods.
    # However, the test `test_backend_interface` in `test_base.py` expects this to raise TypeError
    # upon instantiation if it's actually incomplete. For it to be importable and usable in that
    # test, it must be a valid class definition. The TypeError is raised by Python's ABC mechanism
    # when trying to instantiate an ABC subclass that hasn't implemented all abstract methods.
    # The definition itself is fine; instantiation is where it fails.
    # To ensure this test works as intended, `IncompleteBackend` should lack some of the @abstractmethod implementations.
    # Let's assume for now the test `test_backend_interface` correctly defines or uses an IncompleteBackend
    # that actually lacks some methods for the purpose of that test.
    # The current definition here implements all methods with `pass` or default returns,
    # making it a *complete* implementation for type checking, but the test might dynamically
    # create a truly incomplete one or this one might be sufficient for the test's purpose if
    # the test itself modifies the class attributes or checks `__abstractmethods__`.
    # For this subtask, ensuring type hints are correct is the main goal.
    
    # Making it actually incomplete by removing one method for the sake of example
    # (though this might break the test_base.py if it expects to import this specific one)
    # For now, will keep all methods to ensure it's a valid class, assuming test_base.py handles incompleteness check.
    # The crucial part is that the type hints are correct.
    @override
    def _ensure_connected(self) -> None: pass
    @override
    def insert_usage(self, entry: UsageEntry) -> None: pass
    @override
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats: return UsageStats()
    @override
    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]: return []
    @override
    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]: return {}
    @override
    def purge(self) -> None: pass
    @override
    def tail(self, n: int = 10) -> List[UsageEntry]: return []
    @override
    def close(self) -> None: pass
    @override
    def execute_query(self, query: str) -> List[Dict[str, Any]]: return [{}]
    @override
    def get_usage_limits(self, scope: Optional[LimitScope] = None, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None) -> List[UsageLimitData]: return []
    @override
    def get_accounting_entries_for_quota(self, start_time: datetime, limit_type: LimitType, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None) -> float: return 0.0
    @override
    def insert_usage_limit(self, limit: UsageLimitData) -> None: pass
    # @override # Example: Making it incomplete by commenting out one abstract method
    # def delete_usage_limit(self, limit_id: int) -> None: pass
