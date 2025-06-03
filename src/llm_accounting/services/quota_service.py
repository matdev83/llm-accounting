from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Any

from ..backends.base import BaseBackend
from ..models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO


class QuotaService:
    def __init__(self, backend: BaseBackend):
        self.backend = backend
        self.limits_cache: Optional[List[UsageLimitDTO]] = None
        self._load_limits_from_backend()

    def _load_limits_from_backend(self) -> None:
        """Loads all usage limits from the backend into the cache."""
        self.limits_cache = self.backend.get_usage_limits() # Assuming this fetches all if no args

    def refresh_limits_cache(self) -> None:
        """Refreshes the limits cache from the backend."""
        self.limits_cache = None # Or []
        self._load_limits_from_backend()

    def check_quota(
        self,
        model: str,
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float = 0.0,
        project_name: Optional[str] = None,
        completion_tokens: int = 0,
    ) -> Tuple[bool, Optional[str]]:
        checks = [
            self._check_global_limits,
            self._check_model_limits,
            self._check_project_limits,
            self._check_user_limits,
            self._check_caller_limits,
            self._check_user_caller_limits,
        ]

        for check_method in checks:
            if check_method.__name__ == "_check_project_limits":
                allowed, message = check_method(model, username, caller_name, project_name, input_tokens, cost, completion_tokens)
            else:
                allowed, message = check_method(model, username, caller_name, input_tokens, cost, completion_tokens)
            
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
        completion_tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        if self.limits_cache is None: # Safeguard
            self._load_limits_from_backend()

        limits_to_evaluate = [
            limit for limit in self.limits_cache
            if LimitScope(limit.scope) == LimitScope.GLOBAL
        ]
        return self._evaluate_limits(
            limits_to_evaluate, None, None, None, None, input_tokens, cost, completion_tokens
        )

    def _check_model_limits(
        self,
        model: str,
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        if self.limits_cache is None: # Safeguard
            self._load_limits_from_backend()

        limits_to_evaluate = [
            limit for limit in self.limits_cache
            if LimitScope(limit.scope) == LimitScope.MODEL and limit.model == model
        ]
        return self._evaluate_limits(limits_to_evaluate, model, None, None, None, input_tokens, cost, completion_tokens)

    def _check_project_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        project_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        if not project_name:
            return True, None
        if self.limits_cache is None: # Safeguard
            self._load_limits_from_backend()

        limits_to_evaluate = [
            limit for limit in self.limits_cache
            if LimitScope(limit.scope) == LimitScope.PROJECT and limit.project_name == project_name
        ]
        return self._evaluate_limits(limits_to_evaluate, model, None, None, project_name, input_tokens, cost, completion_tokens)


    def _check_user_limits(
        self,
        model: Optional[str],
        username: str,
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        if not username:
             return True, None
        if self.limits_cache is None: # Safeguard
            self._load_limits_from_backend()

        limits_to_evaluate = [
            limit for limit in self.limits_cache
            if LimitScope(limit.scope) == LimitScope.USER and limit.username == username
        ]
        return self._evaluate_limits(
            limits_to_evaluate, model, username, None, None, input_tokens, cost, completion_tokens
        )

    def _check_caller_limits(
        self,
        model: Optional[str],
        username: Optional[str], # This username is for the request, not the limit's username field here.
        caller_name: str,
        input_tokens: int,
        cost: float,
        completion_tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        if not caller_name:
            return True, None
        if self.limits_cache is None: # Safeguard
            self._load_limits_from_backend()

        # For CALLER scope limits that are *not* specific to a user (i.e., limit.username is None)
        limits_to_evaluate = [
            limit for limit in self.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER
            and limit.caller_name == caller_name
            and limit.username is None # Explicitly for generic caller limits
        ]
        return self._evaluate_limits(
            limits_to_evaluate, model, None, caller_name, None, input_tokens, cost, completion_tokens, limit_scope_for_message="CALLER (caller: {caller_name})"
        )

    def _check_user_caller_limits(
        self,
        model: Optional[str],
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float,
        completion_tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        if not username or not caller_name:
            return True, None
        if self.limits_cache is None: # Safeguard
            self._load_limits_from_backend()

        # For CALLER scope limits that *are* specific to a user (limit.username is not None)
        limits_to_evaluate = [
            limit for limit in self.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER # Scope is still CALLER
            and limit.username == username
            and limit.caller_name == caller_name
        ]
        return self._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, None, input_tokens, cost, completion_tokens
        )

    def _evaluate_limits(
        self, 
        limits: List[UsageLimitDTO],
        request_model: Optional[str],
        request_username: Optional[str],
        request_caller_name: Optional[str],
        project_name_for_usage_sum: Optional[str],
        request_input_tokens: int,
        request_cost: float,
        request_completion_tokens: int,
        limit_scope_for_message: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        now = datetime.now(timezone.utc)
        for limit in limits:
            limit_scope_enum = LimitScope(limit.scope)

            # --- Start: Logic to check if limit applies to the current request ---
            if limit_scope_enum != LimitScope.GLOBAL:
                # If a limit specifies a model, it should only apply if the request is for that model.
                if limit.model and limit.model != request_model:
                    continue
                # If a limit specifies a username, it should only apply if the request is for that username.
                # This is generally ensured by how limits are fetched (e.g., _check_user_limits only fetches for that user),
                # but this check provides an explicit safeguard.
                if limit.username and limit.username != request_username:
                    continue
                # If a limit specifies a caller_name, it should only apply if the request is for that caller.
                if limit.caller_name and limit.caller_name != request_caller_name:
                    continue

                # If a limit specifies a project_name (and is not a generic PROJECT scope for NULL projects):
                if limit.project_name:
                    if limit.project_name != project_name_for_usage_sum: # project_name_for_usage_sum is the request's project
                        continue # Limit is for a specific project, request is for a different project or no project.
                # If a limit is PROJECT scope and for NULL projects (limit.project_name is None):
                # This means the limit applies to requests that *don't* have a project.
                elif limit_scope_enum == LimitScope.PROJECT and limit.project_name is None:
                    if project_name_for_usage_sum is not None: # Request is for a specific project.
                        continue # This limit only applies to requests with no project.
            # --- End: Logic to check if limit applies to the current request ---

            period_start_time = self._get_period_start(now, TimeInterval(limit.interval_unit), limit.interval_value)

            # Initialize final query parameters
            final_usage_query_model: Optional[str] = None
            final_usage_query_username: Optional[str] = None
            final_usage_query_caller_name: Optional[str] = None
            final_usage_query_project_name: Optional[str] = None
            final_usage_query_filter_project_null: Optional[bool] = None


            if limit_scope_enum == LimitScope.GLOBAL:
                # For GLOBAL limits, usage summation must be across everything.
                # All filter parameters for get_accounting_entries_for_quota are kept as None.
                # final_usage_query_filter_project_null is already None by default.
                pass
            else:
                # Set parameters for get_accounting_entries_for_quota based on the limit object's fields
                # This part determines *how to sum usage* for the given non-GLOBAL limit.
                if limit.model is not None:
                    final_usage_query_model = limit.model

                if limit.username is not None:
                    final_usage_query_username = limit.username

                if limit.caller_name is not None:
                    final_usage_query_caller_name = limit.caller_name

                # Project filtering for usage summation for non-GLOBAL limits
                if limit_scope_enum == LimitScope.PROJECT:
                    if limit.project_name is not None: # Limit for a specific project
                        final_usage_query_project_name = limit.project_name
                    else: # Limit for entries with NO project (project_name is NULL in DB)
                        final_usage_query_filter_project_null = True
                elif limit.project_name is not None:
                    # This handles cases where the scope is not PROJECT (e.g. USER, MODEL, CALLER)
                    # but the limit itself is further constrained to usage within a specific project.
                    # Example: A USER limit that only applies to their usage within 'project_x'.
                    final_usage_query_project_name = limit.project_name
                # If limit_scope_enum is not PROJECT and limit.project_name is None,
                # then final_usage_query_project_name remains None (sum usage across all projects for this user/model/caller)
                # and final_usage_query_filter_project_null also remains None (don't specifically filter for NULL projects).

            current_usage = self.backend.get_accounting_entries_for_quota(
                start_time=period_start_time,
                limit_type=LimitType(limit.limit_type),
                model=final_usage_query_model,
                username=final_usage_query_username,
                caller_name=final_usage_query_caller_name,
                project_name=final_usage_query_project_name,
                filter_project_null=final_usage_query_filter_project_null,
            )
            
            request_value = 0.0
            limit_type_enum = LimitType(limit.limit_type)

            if limit_type_enum == LimitType.REQUESTS:
                request_value = 1.0
            elif limit_type_enum == LimitType.INPUT_TOKENS:
                request_value = float(request_input_tokens)
            elif limit_type_enum == LimitType.OUTPUT_TOKENS:
                request_value = float(request_completion_tokens)
            elif limit_type_enum == LimitType.COST:
                request_value = request_cost
            else:
                continue

            potential_usage = current_usage + request_value

            if potential_usage > limit.max_value:
                formatted_max = f"{float(limit.max_value):.2f}"
                
                scope_desc = LimitScope(limit.scope).value.upper()
                
                details = []
                if limit.model: details.append(f"model: {limit.model}")
                if limit.username: details.append(f"user: {limit.username}")
                if limit.caller_name: details.append(f"caller: {limit.caller_name}")
                if limit.project_name: details.append(f"project: {limit.project_name}")
                
                if details:
                    scope_desc += f" ({', '.join(details)})"
                
                limit_unit_str = limit.interval_unit.lower()
                plural_s = "s" if limit.interval_value > 1 and not limit_unit_str.endswith("s") else ""
                
                return (
                    False,
                    f"{scope_desc} limit: {formatted_max} {limit.limit_type} per {limit.interval_value} {limit_unit_str}{plural_s}, current usage: {current_usage:.2f}, request: {request_value:.2f}",
                )
        return True, None

    def _get_period_start(self, current_time: datetime, interval_unit: TimeInterval, interval_value: int) -> datetime:
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        if interval_unit == TimeInterval.SECOND:
            new_second = current_time.second - (current_time.second % interval_value)
            return current_time.replace(second=new_second, microsecond=0)
        elif interval_unit == TimeInterval.MINUTE:
            new_minute = current_time.minute - (current_time.minute % interval_value)
            return current_time.replace(minute=new_minute, second=0, microsecond=0)
        elif interval_unit == TimeInterval.HOUR:
            new_hour = current_time.hour - (current_time.hour % interval_value)
            return current_time.replace(hour=new_hour, minute=0, second=0, microsecond=0)
        elif interval_unit == TimeInterval.DAY:
            if interval_value != 1:
                pass
            start_of_current_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            days_since_epoch = (start_of_current_day - datetime(1970, 1, 1, tzinfo=timezone.utc)).days
            days_offset = days_since_epoch % interval_value
            return start_of_current_day - timedelta(days=days_offset)
        elif interval_unit == TimeInterval.WEEK:
            start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_current_iso_week = start_of_day - timedelta(days=start_of_day.weekday())
            if interval_value == 1:
                return start_of_current_iso_week
            else:
                epoch_week_start = datetime(1970, 1, 5, tzinfo=timezone.utc)
                weeks_since_epoch = (start_of_current_iso_week - epoch_week_start).days // 7
                weeks_offset = weeks_since_epoch % interval_value
                return start_of_current_iso_week - timedelta(weeks=weeks_offset)
        elif interval_unit == TimeInterval.MONTH:
            year = current_time.year
            month = current_time.month
            total_months_current = year * 12 + month -1
            
            months_offset = total_months_current % interval_value
            
            effective_total_months = total_months_current - months_offset
            
            effective_year = effective_total_months // 12
            effective_month = (effective_total_months % 12) + 1
            
            return current_time.replace(year=effective_year, month=effective_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported time interval unit: {interval_unit}")
