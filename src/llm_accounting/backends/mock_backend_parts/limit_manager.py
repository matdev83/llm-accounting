import logging
from datetime import datetime
from typing import List, Optional
# from typing_extensions import override # Removed as it's not directly overriding BaseBackend
from llm_accounting.models.limits import LimitScope, LimitType, UsageLimitDTO  # Corrected import path


class MockLimitManager:
    def __init__(self, parent_backend):
        self.parent_backend = parent_backend

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        """Mocks inserting a usage limit."""
        if limit.id is None:
            limit.id = self.parent_backend.next_limit_id
            self.parent_backend.next_limit_id += 1
        self.parent_backend.limits.append(limit)
        logging.debug(f"MockBackend: Inserted usage limit for scope {limit.scope} with ID {limit.id}")

    def delete_usage_limit(self, limit_id: int) -> None:
        """Mocks deleting a usage limit."""
        initial_len = len(self.parent_backend.limits)
        self.parent_backend.limits = [limit for limit in self.parent_backend.limits if limit.id != limit_id]
        if len(self.parent_backend.limits) < initial_len:
            logging.debug(f"MockBackend: Deleted usage limit with ID {limit_id}")
        else:
            logging.debug(f"MockBackend: No usage limit found with ID {limit_id} to delete.")

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = False,
        filter_username_null: Optional[bool] = False,
        filter_caller_name_null: Optional[bool] = False,
    ) -> List[UsageLimitDTO]:
        """Mocks retrieving usage limits."""
        logging.debug(f"MockBackend: Getting usage limits with filters: scope={scope}, model={model}, username={username}, caller_name={caller_name}, project_name={project_name}, filter_project_null={filter_project_null}, filter_username_null={filter_username_null}, filter_caller_name_null={filter_caller_name_null}")

        filtered_limits = self.parent_backend.limits

        if scope:
            filtered_limits = [limit for limit in filtered_limits if limit.scope == scope.value]
        if model:
            filtered_limits = [limit for limit in filtered_limits if limit.model == model]
        if username:
            filtered_limits = [limit for limit in filtered_limits if limit.username == username]
        if caller_name:
            filtered_limits = [limit for limit in filtered_limits if limit.caller_name == caller_name]
        if project_name:
            filtered_limits = [limit for limit in filtered_limits if limit.project_name == project_name]

        if filter_project_null:
            filtered_limits = [limit for limit in filtered_limits if limit.project_name is None]
        if filter_username_null:
            filtered_limits = [limit for limit in filtered_limits if limit.username is None]
        if filter_caller_name_null:
            filtered_limits = [limit for limit in filtered_limits if limit.caller_name is None]

        return filtered_limits

    def get_accounting_entries_for_quota(
        self,
        start_time: datetime,
        limit_type: LimitType,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = False,
    ) -> float:
        """
        Mocks getting accounting entries for quota calculation.
        """
        logging.debug(f"MockBackend: Getting accounting entries for quota (type: {limit_type.value}) from {start_time} with filters: model={model}, username={username}, caller_name={caller_name}, project_name={project_name}, filter_project_null={filter_project_null}")
        mock_value = 100.0
        if limit_type == LimitType.REQUESTS:
            mock_value = 10.0
        elif limit_type == LimitType.COST:
            mock_value = 5.0

        if model == "specific_model_for_quota_test":
            mock_value /= 2

        return mock_value
