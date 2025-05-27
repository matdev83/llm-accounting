from datetime import datetime, timezone
from typing import Optional, Tuple

from ..backends.base import BaseBackend
from ..models.limits import LimitScope, LimitType, TimeInterval


class QuotaService:
    def __init__(self, backend: BaseBackend):
        self.db = backend

    def check_quota(
        self,
        model: str,
        username: Optional[str], # Made optional as per existing usage
        caller_name: Optional[str], # Made optional
        input_tokens: int,
        cost: float = 0.0,
        project_name: Optional[str] = None, # New field
    ) -> Tuple[bool, Optional[str]]:
        # Check limits in hierarchical order. Project limits could be checked early.
        # For example, after MODEL and before USER.
        checks = [
            self._check_model_limits,
            self._check_project_limits, # Added project limits check
            self._check_global_limits,
            self._check_user_limits,
            self._check_caller_limits,
            self._check_user_caller_limits, # This might need re-evaluation if project is also involved
        ]

        for check_method in checks:
            # For _check_project_limits, we need to pass project_name
            if check_method.__name__ == "_check_project_limits":
                allowed, message = check_method(model, username, caller_name, project_name, input_tokens, cost)
            else:
                allowed, message = check_method(model, username, caller_name, input_tokens, cost)
            
            if not allowed:
                return False, message

        return True, None

    def _check_global_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.db.get_usage_limits(scope=LimitScope.GLOBAL)
        return self._evaluate_limits(
            limits, model, username, caller_name, None, input_tokens, cost # project_name is None for GLOBAL
        )

    def _check_model_limits(
        self,
        model: str, # Model is required for model limits
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.db.get_usage_limits(scope=LimitScope.MODEL, model=model)
        # For MODEL scope, usage is aggregated across all projects for that model.
        return self._evaluate_limits(limits, model, None, None, None, input_tokens, cost)

    def _check_project_limits(
        self,
        model: Optional[str], # Model can be optional if project limit applies to all models
        username: Optional[str],
        caller_name: Optional[str],
        project_name: Optional[str], # Project name is key here
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not project_name: # Cannot check project limits without a project name
            return True, None 
        limits = self.db.get_usage_limits(scope=LimitScope.PROJECT, project_name=project_name)
        # For PROJECT scope, usage is aggregated for that specific project.
        return self._evaluate_limits(limits, model, None, None, project_name, input_tokens, cost)


    def _check_user_limits(
        self,
        model: Optional[str],
        username: str, # Username is required for user limits
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not username:
             return True, None
        limits = self.db.get_usage_limits(scope=LimitScope.USER, username=username)
        # For USER scope, usage is aggregated across all projects for that user.
        return self._evaluate_limits(
            limits, model, username, None, None, input_tokens, cost
        )

    def _check_caller_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: str, # Caller name is required
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not caller_name:
            return True, None
        limits = self.db.get_usage_limits(
            scope=LimitScope.CALLER, caller_name=caller_name
        )
        # For CALLER scope, usage is aggregated across all projects for that caller.
        return self._evaluate_limits(
            limits, model, None, caller_name, None, input_tokens, cost
        )

    def _check_user_caller_limits(
        self,
        model: Optional[str],
        username: str, # Required
        caller_name: str, # Required
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not username or not caller_name:
            return True, None
        limits = self.db.get_usage_limits(
            scope=LimitScope.USER, username=username, caller_name=caller_name # Should be USER_CALLER if such scope existed
                                                                            # Assuming this means a USER limit that also specifies a caller_name
        )
        # This scope's usage aggregation also needs consideration for project.
        # If it's a USER limit that also has a caller_name, it's still user-wide usage.
        return self._evaluate_limits(
            limits, model, username, caller_name, None, input_tokens, cost
        )

    def _evaluate_limits(
        self, limits, model, username, caller_name, project_name_for_usage_sum, input_tokens, cost
    ):
        now = datetime.now(timezone.utc)
        for limit in limits:
            # Determine project_name to pass to _get_usage based on limit's scope
            usage_project_filter = None
            if limit.scope == LimitScope.PROJECT.value: # Use project_name from the limit itself
                usage_project_filter = limit.project_name 
            # For other scopes (GLOBAL, USER, MODEL, CALLER), usage is typically aggregated *across* all projects,
            # unless the specific check method (e.g. _check_project_limits) has already passed a project_name_for_usage_sum.
            # The `project_name_for_usage_sum` argument helps clarify this.
            # If a project limit is being evaluated, sum usage *for that project*.
            # If a global/user/model limit is evaluated, sum usage *globally/per-user/per-model* (i.e. project_name_for_usage_sum=None).
            
            # The key is: when summing usage for a specific limit, what context does that sum apply to?
            # If the limit is a PROJECT limit, sum usage FOR THAT PROJECT.
            # If the limit is a USER limit, sum usage FOR THAT USER (across all their projects).
            # `project_name_for_usage_sum` is passed by each `_check_..._limits` method.
            # For _check_project_limits, it passes the project name. For others, it passes None.

            start_time = now  # Default, will be adjusted if time_delta is valid
            try:
                delta = limit.time_delta()
                start_time = now - delta
            except NotImplementedError: # Handle monthly limits specifically
                if limit.interval_unit == TimeInterval.MONTH.value:
                    # Calculate start of current month in UTC
                    today_utc = datetime.now(timezone.utc)
                    start_time = today_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                else: # Should not happen if time_delta is correctly implemented for other units
                    raise

            current_usage = self._get_usage(
                limit.limit_type,
                start_time,
                model=limit.model if limit.scope == LimitScope.MODEL.value else model, # For model-specific limits, use the limit's model
                username=username if limit.scope == LimitScope.USER.value else None,
                caller_name=caller_name if limit.scope == LimitScope.CALLER.value else None,
                project_name=usage_project_filter # Use the project name from the limit if it's a project-scope limit
            )

            potential_usage = current_usage
            if limit.limit_type == LimitType.REQUESTS.value:
                potential_usage += 1
            elif limit.limit_type == LimitType.INPUT_TOKENS.value:
                potential_usage += input_tokens
            elif limit.limit_type == LimitType.COST.value:
                potential_usage += cost
            # OUTPUT_TOKENS limits are typically checked after response, not covered by this pre-check

            if potential_usage > limit.max_value:
                scope_name = limit.scope.upper() if isinstance(limit.scope, str) else limit.scope.value.upper()
                limit_details = f" for model '{limit.model}'" if limit.scope == LimitScope.MODEL.value and limit.model else ""
                limit_details += f" for project '{limit.project_name}'" if limit.scope == LimitScope.PROJECT.value and limit.project_name else ""
                # If it's a project scope limit and a model is specified, include model details
                if limit.scope == LimitScope.PROJECT.value and limit.model:
                    limit_details += f" for model '{limit.model}'"
                # ... add more details for USER, CALLER if needed for message clarity ...
                
                return (
                    False,
                    (f"{scope_name} limit exceeded{limit_details}. "
                     f"Max: {float(limit.max_value):.2f} {limit.limit_type} "
                     f"per {limit.interval_value} {limit.interval_unit}."),
                )
        return True, None

    def _get_usage(
        self,
        limit_type: str, # Should be LimitType Enum or its value
        start_time: datetime,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None, # New field
    ) -> float:
        # Ensure limit_type is an Enum member if it's a string
        actual_limit_type = LimitType(limit_type) if isinstance(limit_type, str) else limit_type

        return self.db.get_accounting_entries_for_quota(
            start_time=start_time,
            limit_type=actual_limit_type,
            model=model,
            username=username,
            caller_name=caller_name,
            project_name=project_name, # Pass to backend
        )
