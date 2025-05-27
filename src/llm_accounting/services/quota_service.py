from datetime import datetime, timedelta, timezone # Added timedelta
from typing import Optional, Tuple, List # Added List

from ..backends.base import BaseBackend
# Added UsageLimitData and TimeInterval, assuming LimitScope and LimitType are already there
from ..models.limits import LimitScope, LimitType, TimeInterval, UsageLimitData


class QuotaService:
    def __init__(self, backend: BaseBackend):
        self.backend = backend # Renamed from self.db to self.backend for clarity

    def check_quota(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int, # Assuming this is the primary token count for requests
        cost: float = 0.0,
        # output_tokens: Optional[int] = None, # Add if needed for specific limit types
        # total_tokens: Optional[int] = None,  # Add if needed
    ) -> Tuple[bool, Optional[str]]:
        # Fetch all potentially relevant limits in one go or per scope type.
        # For simplicity, fetching per specific scope attributes as per original logic.
        # Order of checks determines precedence.
        
        # Check MODEL specific limits first
        model_limits = self.backend.get_usage_limits(scope=LimitScope.MODEL, model=model)
        allowed, message = self._evaluate_limits(model_limits, model, username, caller_name, input_tokens, cost, "MODEL")
        if not allowed:
            return False, message

        # Check USER specific limits
        user_limits = self.backend.get_usage_limits(scope=LimitScope.USER, username=username)
        allowed, message = self._evaluate_limits(user_limits, model, username, caller_name, input_tokens, cost, "USER")
        if not allowed:
            return False, message

        # Check CALLER specific limits (just by caller_name)
        caller_only_limits = self.backend.get_usage_limits(scope=LimitScope.CALLER, caller_name=caller_name, username=None)
        allowed, message = self._evaluate_limits(caller_only_limits, model, username, caller_name, input_tokens, cost, "CALLER")
        if not allowed:
            return False, message
            
        # Check USER+CALLER specific limits
        user_caller_limits = self.backend.get_usage_limits(scope=LimitScope.CALLER, username=username, caller_name=caller_name)
        allowed, message = self._evaluate_limits(user_caller_limits, model, username, caller_name, input_tokens, cost, "CALLER") # Scope description is CALLER
        if not allowed:
            return False, message

        # Check GLOBAL limits last
        global_limits = self.backend.get_usage_limits(scope=LimitScope.GLOBAL)
        allowed, message = self._evaluate_limits(global_limits, model, username, caller_name, input_tokens, cost, "GLOBAL")
        if not allowed:
            return False, message
            
        return True, None

    def _evaluate_limits(
        self, 
        limits: List[UsageLimitData], # Explicitly type hint limits
        request_model: str, # Renamed for clarity from 'model'
        request_username: str, # Renamed for clarity
        request_caller_name: str, # Renamed for clarity
        request_input_tokens: int, # Renamed for clarity
        request_cost: float, # Renamed for clarity
        limit_scope_for_message: str # The scope string to use in denial messages for this batch of limits
    ) -> Tuple[bool, Optional[str]]:
        now = datetime.now(timezone.utc)
        for limit in limits:
            try:
                interval_unit_enum = TimeInterval(limit.interval_unit)
            except ValueError:
                # Log this error, skip this malformed limit
                # logger.error(f"Invalid time interval unit in limit ID {limit.id}: {limit.interval_unit}")
                continue # Skip malformed limit

            period_start_time = self._get_period_start(now, interval_unit_enum, limit.interval_value)

            # Determine query parameters for fetching usage based on the limit's specific definition
            usage_query_model = limit.model
            usage_query_username = limit.username
            usage_query_caller_name = limit.caller_name
            
            # For GLOBAL limits, all query params should be None to get total usage for that limit_type
            if LimitScope(limit.scope) == LimitScope.GLOBAL:
                usage_query_model = None
                usage_query_username = None
                usage_query_caller_name = None
            # For MODEL scope, only model should be set from the limit definition
            elif LimitScope(limit.scope) == LimitScope.MODEL:
                usage_query_username = None
                usage_query_caller_name = None
            # For USER scope, only username
            elif LimitScope(limit.scope) == LimitScope.USER:
                usage_query_model = None
                usage_query_caller_name = None
            # For CALLER scope, it could be just caller, or user+caller
            elif LimitScope(limit.scope) == LimitScope.CALLER:
                usage_query_model = None # Caller limits are not per-model unless also model-scoped (which is not standard here)
                # If limit.username is None, it's a general caller limit.
                # If limit.username is set, it's a user+caller limit. query_username is already set to limit.username.

            current_usage = self.backend.get_accounting_entries_for_quota(
                start_time=period_start_time,
                limit_type=LimitType(limit.limit_type), # Convert string from UsageLimitData to Enum
                model=usage_query_model,
                username=usage_query_username,
                caller_name=usage_query_caller_name,
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
                # logger.error(f"Unknown limit type for request value calculation: {limit.limit_type}")
                continue # Skip limit if type is unknown for calculation

            potential_usage = current_usage + request_value

            if potential_usage > limit.max_value:
                formatted_max = f"{float(limit.max_value):.2f}"
                scope_desc = limit_scope_for_message # Use the passed scope description
                
                details = []
                if limit.model: details.append(f"model: {limit.model}")
                if limit.username: details.append(f"user: {limit.username}")
                if limit.caller_name: details.append(f"caller: {limit.caller_name}")
                if details and limit_scope_for_message not in ["GLOBAL"]: # Don't add details for GLOBAL scope message
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
            # For N-day intervals, we need to be careful. If interval_value=1, it's start of day.
            # If interval_value=N, it's start of N-day block, which is more complex.
            # Assuming for DAY, interval_value is typically 1.
            if interval_value != 1:
                # logger.warning("N-day intervals > 1 day are not fully standard for 'DAY' unit, use 'WEEK' or careful calculation.")
                pass # Allow, but might not align with user expectation of "N days ago" vs "start of N-day block"
            # This calculation gives start of current day, then subtracts days to get to start of N-day block
            start_of_current_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            days_since_epoch = (start_of_current_day - datetime(1970, 1, 1, tzinfo=timezone.utc)).days
            days_offset = days_since_epoch % interval_value
            return start_of_current_day - timedelta(days=days_offset)
        elif interval_unit == TimeInterval.WEEK:
            start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            # For N-week intervals
            start_of_current_iso_week = start_of_day - timedelta(days=start_of_day.weekday())
            if interval_value == 1:
                return start_of_current_iso_week
            else:
                # Calculate weeks since an arbitrary epoch week, then find start of N-week block
                epoch_week_start = datetime(1970, 1, 5, tzinfo=timezone.utc) # A Monday
                weeks_since_epoch = (start_of_current_iso_week - epoch_week_start).days // 7
                weeks_offset = weeks_since_epoch % interval_value
                return start_of_current_iso_week - timedelta(weeks=weeks_offset)
        elif interval_unit == TimeInterval.MONTH:
            # For N-month intervals
            year = current_time.year
            month = current_time.month
            # Calculate months since an epoch (e.g., year 0, month 1)
            total_months_current = year * 12 + month -1 # 0-indexed months
            
            months_offset = total_months_current % interval_value
            
            # Subtract the offset from the current total_months_current
            effective_total_months = total_months_current - months_offset
            
            effective_year = effective_total_months // 12
            effective_month = (effective_total_months % 12) + 1 # 1-indexed month
            
            return current_time.replace(year=effective_year, month=effective_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported time interval unit: {interval_unit}")
