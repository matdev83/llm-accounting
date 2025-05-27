from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Any

from ..backends.base import BaseBackend
from ..models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO


class QuotaService:
    def __init__(self, backend: BaseBackend):
        self.backend = backend

    def check_quota(
        self,
        model: str,
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float = 0.0,
        project_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        checks = [
            self._check_model_limits,
            self._check_project_limits,
            self._check_global_limits,
            self._check_user_limits,
            self._check_caller_limits,
            self._check_user_caller_limits,
        ]

        for check_method in checks:
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
        limits = self.backend.get_usage_limits(scope=LimitScope.GLOBAL)
        return self._evaluate_limits(
            limits, None, None, None, None, input_tokens, cost
        )

    def _check_model_limits(
        self,
        model: str,
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.backend.get_usage_limits(scope=LimitScope.MODEL, model=model)
        return self._evaluate_limits(limits, model, None, None, None, input_tokens, cost)

    def _check_project_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        project_name: Optional[str],
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not project_name:
            return True, None 
        limits = self.backend.get_usage_limits(scope=LimitScope.PROJECT, project_name=project_name)
        return self._evaluate_limits(limits, model, None, None, project_name, input_tokens, cost)


    def _check_user_limits(
        self,
        model: Optional[str],
        username: str,
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not username:
             return True, None
        limits = self.backend.get_usage_limits(scope=LimitScope.USER, username=username)
        return self._evaluate_limits(
            limits, model, username, None, None, input_tokens, cost
        )

    def _check_caller_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: str,
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not caller_name:
            return True, None
        limits = self.backend.get_usage_limits(
            scope=LimitScope.CALLER, caller_name=caller_name, username=None, filter_username_null=True
        )
        return self._evaluate_limits(
            limits, model, None, caller_name, None, input_tokens, cost, limit_scope_for_message="CALLER (caller: {caller_name})"
        )

    def _check_user_caller_limits(
        self,
        model: Optional[str],
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        if not username or not caller_name:
            return True, None
        limits = self.backend.get_usage_limits(
            scope=LimitScope.CALLER, username=username, caller_name=caller_name
        )
        return self._evaluate_limits(
            limits, model, username, caller_name, None, input_tokens, cost
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
        limit_scope_for_message: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        now = datetime.now(timezone.utc)
        for limit in limits:
            period_start_time = self._get_period_start(now, TimeInterval(limit.interval_unit), limit.interval_value)

            usage_query_model = None
            usage_query_username = None
            usage_query_caller_name = None
            usage_query_project_name = None

            # Determine parameters for get_accounting_entries_for_quota based on limit scope
            usage_query_model = None
            usage_query_username = None
            usage_query_caller_name = None
            usage_query_project_name = None
            usage_query_filter_project_null = None

            limit_scope_enum = LimitScope(limit.scope)

            if limit_scope_enum == LimitScope.GLOBAL:
                # For global limits, sum across all entities (no specific filters)
                pass
            elif limit_scope_enum == LimitScope.MODEL:
                usage_query_model = limit.model
            elif limit_scope_enum == LimitScope.USER:
                usage_query_username = limit.username
            elif limit_scope_enum == LimitScope.CALLER:
                usage_query_caller_name = limit.caller_name
                usage_query_username = limit.username # For user-caller combination limits
            elif limit_scope_enum == LimitScope.PROJECT:
                if limit.project_name is not None:
                    usage_query_project_name = limit.project_name
                else:
                    usage_query_filter_project_null = True # Project limit for entries with NULL project
                
                # If a project limit is also scoped to a model, include that filter
                if limit.model:
                    usage_query_model = limit.model

            # The project_name_for_usage_sum parameter is now redundant and can be removed from the signature
            # as the logic for project filtering is now fully derived from the limit object itself.
            # However, to avoid changing the signature of _evaluate_limits for now, we'll keep it but ignore it.

            current_usage = self.backend.get_accounting_entries_for_quota(
                start_time=period_start_time,
                limit_type=LimitType(limit.limit_type),
                model=usage_query_model,
                username=usage_query_username,
                caller_name=usage_query_caller_name,
                project_name=usage_query_project_name,
                filter_project_null=usage_query_filter_project_null,
            )
            
            request_value = 0.0
            limit_type_enum = LimitType(limit.limit_type)

            if limit_type_enum == LimitType.REQUESTS:
                request_value = 1.0
            elif limit_type_enum == LimitType.INPUT_TOKENS:
                request_value = float(request_input_tokens)
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
