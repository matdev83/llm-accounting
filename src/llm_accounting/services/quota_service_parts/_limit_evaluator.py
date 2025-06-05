import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

from ...backends.base import BaseBackend
from ...models.limits import LimitType, TimeInterval, UsageLimitDTO, LimitScope

class QuotaServiceLimitEvaluator:
    def __init__(self, backend: BaseBackend):
        self.backend = backend

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
        now = datetime.now(timezone.utc) # Keep timezone-aware
        for limit in limits:
            limit_scope_enum = LimitScope(limit.scope)

            # --- Start: Logic to check if limit applies to the current request ---
            if limit_scope_enum != LimitScope.GLOBAL:
                # If a limit specifies a model, it should only apply if the request is for that model.
                if limit.model and limit.model != request_model:
                    continue
                # If a limit specifies a username, it should only apply if the request is for that username.
                if limit.username and limit.username != request_username:
                    continue
                # If a limit specifies a caller_name, it should only apply if the request is for that caller.
                if limit.caller_name and limit.caller_name != request_caller_name:
                    continue

                # If a limit specifies a project_name (and is not a generic PROJECT scope for NULL projects):
                if limit.project_name:
                    if limit.project_name != project_name_for_usage_sum:
                        continue
                # If a limit is PROJECT scope and for NULL projects (limit.project_name is None):
                elif limit_scope_enum == LimitScope.PROJECT and limit.project_name is None:
                    if project_name_for_usage_sum is not None:
                        continue
            # --- End: Logic to check if limit applies to the current request ---

            interval_unit_enum = TimeInterval(limit.interval_unit) # Get enum member
            period_start_time = self._get_period_start(now, interval_unit_enum, limit.interval_value)

            # Calculate query_end_time
            if interval_unit_enum.is_rolling():
                query_end_time = now
            else:
                # For fixed intervals, query_end_time is the actual end of the period
                duration: timedelta
                if interval_unit_enum == TimeInterval.MONTH:
                    # Calculate end of month correctly
                    # Calculate the start of the next period directly
                    start_year = period_start_time.year
                    start_month = period_start_time.month # 1-indexed

                    # Add interval_value months to the start month
                    next_period_raw_month = start_month + limit.interval_value

                    # Adjust year and month
                    next_period_year = start_year + (next_period_raw_month - 1) // 12
                    next_period_month = (next_period_raw_month - 1) % 12 + 1

                    query_end_time = datetime(next_period_year, next_period_month, 1, tzinfo=period_start_time.tzinfo)
                elif interval_unit_enum == TimeInterval.WEEK:
                    duration = timedelta(weeks=limit.interval_value)
                    query_end_time = period_start_time + duration
                else: # SECOND, MINUTE, HOUR, DAY
                    simple_interval_map = {
                        TimeInterval.SECOND.value: timedelta(seconds=1),
                        TimeInterval.MINUTE.value: timedelta(minutes=1),
                        TimeInterval.HOUR.value: timedelta(hours=1),
                        TimeInterval.DAY.value: timedelta(days=1),
                    }
                    base_delta = simple_interval_map.get(interval_unit_enum.value)
                    if not base_delta:
                        raise ValueError(f"Unsupported fixed time interval unit for duration: {interval_unit_enum.value}")
                    duration = base_delta * limit.interval_value
                    query_end_time = period_start_time + duration

            # query_end_time should include the current moment with full
            # precision to avoid excluding entries recorded within the same
            # second.  Do not truncate microseconds.

            final_usage_query_model: Optional[str] = None
            final_usage_query_username: Optional[str] = None
            final_usage_query_caller_name: Optional[str] = None
            final_usage_query_project_name: Optional[str] = None
            final_usage_query_filter_project_null: Optional[bool] = None

            if limit_scope_enum == LimitScope.GLOBAL:
                pass
            else:
                if limit.model is not None:
                    final_usage_query_model = limit.model

                if limit.username is not None:
                    final_usage_query_username = limit.username

                if limit.caller_name is not None:
                    final_usage_query_caller_name = limit.caller_name

                if limit_scope_enum == LimitScope.PROJECT:
                    if limit.project_name is not None:
                        final_usage_query_project_name = limit.project_name
                    else:
                        final_usage_query_filter_project_null = True
                elif limit.project_name is not None:
                    final_usage_query_project_name = limit.project_name

            current_usage = self.backend.get_accounting_entries_for_quota(
                start_time=period_start_time,
                end_time=query_end_time,
                limit_type=LimitType(limit.limit_type),
                interval_unit=TimeInterval(limit.interval_unit), # Pass the interval_unit
                model=final_usage_query_model,
                username=final_usage_query_username,
                caller_name=final_usage_query_caller_name,
                project_name=final_usage_query_project_name,
                filter_project_null=final_usage_query_filter_project_null,
            )

            limit_type_enum = LimitType(limit.limit_type)
            request_value: float
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

            # Convert to float for comparison, and round to avoid floating point inaccuracies
            # Assuming costs and token counts are typically integers or have limited decimal places.
            # Using a precision of 6 decimal places should be sufficient for most cases.
            potential_usage_float = round(float(potential_usage), 6)
            limit_max_value_float = round(float(limit.max_value), 6)

            # Compare with a small epsilon to account for floating point inaccuracies
            # If potential_usage is slightly above max_value due to precision, it should still trigger.
            # Using a direct comparison after rounding is generally safer than epsilon for >
            comparison_result = potential_usage_float > limit_max_value_float

            if comparison_result:
                scope_msg = limit_scope_for_message if limit_scope_for_message else limit.scope
                if limit.scope == LimitScope.USER.value and limit.username:
                    scope_msg = f"USER (user: {limit.username})"
                elif limit.scope == LimitScope.MODEL.value and limit.model:
                    scope_msg = f"MODEL (model: {limit.model})"
                elif limit.scope == LimitScope.CALLER.value and limit.caller_name:
                    if limit.username:
                        scope_msg = f"CALLER (user: {limit.username}, caller: {limit.caller_name})"
                    else:
                        scope_msg = f"CALLER (caller: {limit.caller_name})"
                elif limit.scope == LimitScope.PROJECT.value:
                    if limit.project_name:
                        scope_msg = f"PROJECT (project: {limit.project_name})"
                    else:
                        scope_msg = "PROJECT (no project)"

                reason_message = (
                    f"{scope_msg} limit: {limit.max_value:.2f} {limit.limit_type} per {limit.interval_value} {limit.interval_unit}"
                    f" exceeded. Current usage: {current_usage:.2f}, request: {request_value:.2f}."
                )
                return False, reason_message # Original return for exceeded limit
        return True, None # Original return for no limit exceeded

    def _evaluate_limits_enhanced(
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
    ) -> Tuple[bool, Optional[str], Optional[datetime]]: # Changed return type
        now = datetime.now(timezone.utc) # Keep timezone-aware
        for limit in limits:
            limit_scope_enum = LimitScope(limit.scope)

            # --- Start: Logic to check if limit applies to the current request ---
            if limit_scope_enum != LimitScope.GLOBAL:
                # If a limit specifies a model, it should only apply if the request is for that model.
                if limit.model and limit.model != request_model:
                    continue
                # If a limit specifies a username, it should only apply if the request is for that username.
                if limit.username and limit.username != request_username:
                    continue
                # If a limit specifies a caller_name, it should only apply if the request is for that caller.
                if limit.caller_name and limit.caller_name != request_caller_name:
                    continue

                # If a limit specifies a project_name (and is not a generic PROJECT scope for NULL projects):
                if limit.project_name:
                    if limit.project_name != project_name_for_usage_sum:
                        continue
                # If a limit is PROJECT scope and for NULL projects (limit.project_name is None):
                elif limit_scope_enum == LimitScope.PROJECT and limit.project_name is None:
                    if project_name_for_usage_sum is not None:
                        continue
            # --- End: Logic to check if limit applies to the current request ---

            interval_unit_enum = TimeInterval(limit.interval_unit) # Get enum member
            period_start_time = self._get_period_start(now, interval_unit_enum, limit.interval_value)

            # Calculate query_end_time (which will be the reset_timestamp for fixed intervals)
            if interval_unit_enum.is_rolling():
                # For rolling, the reset time is when the oldest entry in the window expires.
                # This is period_start_time + interval_duration.
                # The period_start_time is already calculated relative to 'now'.
                # So, period_end_for_retry is the absolute time when the current window "rolls over".
                period_end_for_retry: datetime
                if interval_unit_enum == TimeInterval.MONTH_ROLLING:
                    year = period_start_time.year
                    month = period_start_time.month
                    target_month_val = month + limit.interval_value
                    target_year_val = year
                    while target_month_val > 12:
                        target_month_val -= 12
                        target_year_val += 1
                    period_end_for_retry = period_start_time.replace(year=target_year_val, month=target_month_val)
                elif interval_unit_enum == TimeInterval.WEEK_ROLLING:
                    period_end_for_retry = period_start_time + timedelta(weeks=limit.interval_value)
                elif interval_unit_enum == TimeInterval.DAY_ROLLING:
                    period_end_for_retry = period_start_time + timedelta(days=limit.interval_value)
                elif interval_unit_enum == TimeInterval.HOUR_ROLLING:
                    period_end_for_retry = period_start_time + timedelta(hours=limit.interval_value)
                elif interval_unit_enum == TimeInterval.MINUTE_ROLLING:
                    period_end_for_retry = period_start_time + timedelta(minutes=limit.interval_value)
                elif interval_unit_enum == TimeInterval.SECOND_ROLLING:
                    period_end_for_retry = period_start_time + timedelta(seconds=limit.interval_value)
                else:
                    raise ValueError(f"Unsupported rolling time interval unit for retry calculation: {interval_unit_enum.value}")
                reset_timestamp = period_end_for_retry
            else: # Non-rolling (fixed) intervals
                # For fixed intervals, the reset time is the end of the current fixed period.
                duration: timedelta
                if interval_unit_enum == TimeInterval.MONTH:
                    start_year = period_start_time.year
                    start_month = period_start_time.month
                    next_period_raw_month = start_month + limit.interval_value
                    next_period_year = start_year + (next_period_raw_month - 1) // 12
                    next_period_month = (next_period_raw_month - 1) % 12 + 1
                    reset_timestamp = datetime(next_period_year, next_period_month, 1, 0, 0, 0, tzinfo=period_start_time.tzinfo)
                elif interval_unit_enum == TimeInterval.WEEK:
                    duration = timedelta(weeks=limit.interval_value)
                    reset_timestamp = period_start_time + duration
                else: # SECOND, MINUTE, HOUR, DAY
                    simple_interval_map = {
                        TimeInterval.SECOND.value: timedelta(seconds=1),
                        TimeInterval.MINUTE.value: timedelta(minutes=1),
                        TimeInterval.HOUR.value: timedelta(hours=1),
                        TimeInterval.DAY.value: timedelta(days=1),
                    }
                    base_delta = simple_interval_map.get(interval_unit_enum.value)
                    if not base_delta:
                        raise ValueError(f"Unsupported fixed time interval unit for duration: {interval_unit_enum.value}")
                    duration = base_delta * limit.interval_value
                    reset_timestamp = period_start_time + duration
            
            # Ensure reset_timestamp is truncated for consistency
            reset_timestamp = reset_timestamp.replace(microsecond=0)

            final_usage_query_model: Optional[str] = None
            final_usage_query_username: Optional[str] = None
            final_usage_query_caller_name: Optional[str] = None
            final_usage_query_project_name: Optional[str] = None
            final_usage_query_filter_project_null: Optional[bool] = None

            if limit_scope_enum == LimitScope.GLOBAL:
                pass
            else:
                if limit.model is not None:
                    final_usage_query_model = limit.model

                if limit.username is not None:
                    final_usage_query_username = limit.username

                if limit.caller_name is not None:
                    final_usage_query_caller_name = limit.caller_name

                if limit_scope_enum == LimitScope.PROJECT:
                    if limit.project_name is not None:
                        final_usage_query_project_name = limit.project_name
                    else:
                        final_usage_query_filter_project_null = True
                elif limit.project_name is not None:
                    final_usage_query_project_name = limit.project_name

            # Add logging here
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Evaluating limit: {limit.limit_type} for {limit.scope} (model: {limit.model}, user: {limit.username}, project: {limit.project_name})")
            logger.debug(f"Period start: {period_start_time}, Query end (now): {now}")

            current_usage = self.backend.get_accounting_entries_for_quota(
                start_time=period_start_time,
                end_time=now,  # Always query up to 'now' for current usage with full precision
                limit_type=LimitType(limit.limit_type),
                interval_unit=TimeInterval(limit.interval_unit), # Pass the interval_unit
                model=final_usage_query_model,
                username=final_usage_query_username,
                caller_name=final_usage_query_caller_name,
                project_name=final_usage_query_project_name,
                filter_project_null=final_usage_query_filter_project_null,
            )
            logger.debug(f"Current usage calculated: {current_usage}")

            limit_type_enum = LimitType(limit.limit_type)
            request_value: float
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

            # Convert to float for comparison, and round to avoid floating point inaccuracies
            # Using a precision of 6 decimal places should be sufficient for most cases.
            potential_usage_float = round(float(potential_usage), 6)
            limit_max_value_float = round(float(limit.max_value), 6)

            # Compare with a small epsilon to account for floating point inaccuracies
            comparison_result = potential_usage_float > limit_max_value_float

            if comparison_result:
                scope_msg = limit_scope_for_message if limit_scope_for_message else limit.scope
                if limit.scope == LimitScope.USER.value and limit.username:
                    scope_msg = f"USER (user: {limit.username})"
                elif limit.scope == LimitScope.MODEL.value and limit.model:
                    scope_msg = f"MODEL (model: {limit.model})"
                elif limit.scope == LimitScope.CALLER.value and limit.caller_name:
                    if limit.username:
                        scope_msg = f"CALLER (user: {limit.username}, caller: {limit.caller_name})"
                    else:
                        scope_msg = f"CALLER (caller: {limit.caller_name})"
                elif limit.scope == LimitScope.PROJECT.value:
                    if limit.project_name:
                        scope_msg = f"PROJECT (project: {limit.project_name})"
                    else:
                        scope_msg = "PROJECT (no project)"

                reason_message = (
                    f"{scope_msg} limit: {limit.max_value:.2f} {limit.limit_type} per {limit.interval_value} {limit.interval_unit}"
                    f" exceeded. Current usage: {current_usage:.2f}, request: {request_value:.2f}."
                )
                return False, reason_message, reset_timestamp # Return reset_timestamp
        return True, None, None # Return None for reset_timestamp if allowed

    def _get_period_start(self, current_time: datetime, interval_unit: TimeInterval, interval_value: int) -> datetime:
        # Ensure current_time is UTC-aware for consistent calculations
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Truncate current_time to second precision for consistent rolling window calculations
        current_time_truncated = current_time.replace(microsecond=0)

        if interval_unit == TimeInterval.SECOND:
            new_second = current_time_truncated.second - (current_time_truncated.second % interval_value)
            period_start = current_time_truncated.replace(second=new_second, microsecond=0)
        elif interval_unit == TimeInterval.MINUTE:
            new_minute = current_time_truncated.minute - (current_time_truncated.minute % interval_value)
            period_start = current_time_truncated.replace(minute=new_minute, second=0, microsecond=0)
        elif interval_unit == TimeInterval.HOUR:
            new_hour = current_time_truncated.hour - (current_time_truncated.hour % interval_value)
            period_start = current_time_truncated.replace(hour=new_hour, minute=0, second=0, microsecond=0)
        elif interval_unit == TimeInterval.DAY:
            # The calculation below handles any interval_value, so no special-case logic is required.
            start_of_current_day = current_time_truncated.replace(hour=0, minute=0, second=0, microsecond=0)
            epoch_start = datetime(1970, 1, 1, tzinfo=timezone.utc)
            days_since_epoch = (start_of_current_day - epoch_start).days
            days_offset = days_since_epoch % interval_value
            period_start = start_of_current_day - timedelta(days=days_offset)
        elif interval_unit == TimeInterval.WEEK:
            start_of_day = current_time_truncated.replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_current_iso_week = start_of_day - timedelta(days=start_of_day.weekday())
            if interval_value == 1:
                period_start = start_of_current_iso_week
            else:
                epoch_week_start = datetime(1970, 1, 5, tzinfo=timezone.utc) # A Monday
                weeks_since_epoch = (start_of_current_iso_week - epoch_week_start).days // 7
                weeks_offset = weeks_since_epoch % interval_value
                period_start = start_of_current_iso_week - timedelta(weeks=weeks_offset)
        elif interval_unit == TimeInterval.MONTH:
            # Calculate the start of the current interval based on interval_value
            # For example, if interval_value is 3 (quarterly), it should find the start of the current quarter.
            year = current_time_truncated.year
            month = current_time_truncated.month
            
            # Calculate the number of months from year 0 to current month
            total_months_since_epoch = year * 12 + month - 1 # 0-indexed month from year 0
            
            # Find the start of the current interval block
            interval_start_month_index = (total_months_since_epoch // interval_value) * interval_value
            
            # Convert back to year and month
            start_year = interval_start_month_index // 12
            start_month = (interval_start_month_index % 12) + 1 # 1-indexed month
            
            period_start = current_time_truncated.replace(year=start_year, month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif interval_unit.is_rolling(): # Covers all rolling types
             # Common logic for all _ROLLING types from _get_period_start
            delta_map = {
                TimeInterval.SECOND_ROLLING: timedelta(seconds=interval_value),
                TimeInterval.MINUTE_ROLLING: timedelta(minutes=interval_value),
                TimeInterval.HOUR_ROLLING: timedelta(hours=interval_value),
                TimeInterval.DAY_ROLLING: timedelta(days=interval_value),
                TimeInterval.WEEK_ROLLING: timedelta(weeks=interval_value),
            }
            if interval_unit == TimeInterval.MONTH_ROLLING:
                year = current_time_truncated.year
                month = current_time_truncated.month
                target_month = month - interval_value
                target_year = year
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1
                period_start = current_time_truncated.replace(year=target_year, month=target_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            elif interval_unit in delta_map:
                 period_start = (current_time_truncated - delta_map[interval_unit])
            else: # Should not be reached if all rolling types are in map or handled
                raise ValueError(f"Unsupported rolling time interval unit in _get_period_start: {interval_unit}")
        else:
            raise ValueError(f"Unsupported time interval unit: {interval_unit}")
        return period_start
