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
    ) -> Tuple[bool, Optional[str], Optional[int]]:
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
                query_end_time = now.replace(microsecond=0)
            else:
                # For fixed intervals, query_end_time is the actual end of the period
                duration: timedelta
                if interval_unit_enum == TimeInterval.MONTH:
                    # Calculate end of month correctly
                    year = period_start_time.year
                    month = period_start_time.month
                    # Advance by interval_value months
                    total_months = month + limit.interval_value -1 # 0-indexed month for calculation
                    end_year = year + total_months // 12
                    end_month = (total_months % 12) + 1
                    
                    # Find the first day of the next period
                    if end_month == 12:
                        query_end_time = period_start_time.replace(year=end_year + 1, month=1, day=1)
                    else:
                        query_end_time = period_start_time.replace(year=end_year, month=end_month + 1, day=1)
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
            
            # Ensure query_end_time is also truncated for consistency if it came from 'now'
            query_end_time = query_end_time.replace(microsecond=0)

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
            
            potential_usage_float = float(potential_usage)
            limit_max_value_float = float(limit.max_value)
            
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

                retry_after_seconds: Optional[int] = None
                if interval_unit_enum.is_rolling():
                    period_end_for_retry: datetime
                    # For rolling intervals, the period_end_for_retry is period_start_time + interval_duration.
                    # period_start_time for rolling intervals is calculated as (current_time_truncated - interval_duration).
                    # So, period_start_time + interval_duration is the time when the specific window,
                    # that caused the quota check, will end relative to its start.

                    if interval_unit_enum == TimeInterval.MONTH_ROLLING:
                        # period_start_time for MONTH_ROLLING is already set to the first day, 00:00:00 of the start month.
                        # We need to add 'interval_value' months to this.
                        year = period_start_time.year
                        month = period_start_time.month

                        target_month_val = month + limit.interval_value
                        target_year_val = year

                        # Adjust year and month if target_month_val exceeds 12
                        while target_month_val > 12:
                            target_month_val -= 12
                            target_year_val += 1

                        # period_end_for_retry must retain all components of period_start_time (day, hour, min, sec)
                        # and only advance the month and year.
                        # Since _get_period_start for MONTH_ROLLING sets day=1, hour=0, minute=0, second=0, microsecond=0,
                        # this will result in the start of the month 'limit.interval_value' months after period_start_time.
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
                        # This case should ideally not be reached if is_rolling() is comprehensive
                        # and all rolling types are handled above.
                        raise ValueError(f"Unsupported rolling time interval unit for retry calculation: {interval_unit_enum.value}")

                    retry_after_seconds = max(0, int((period_end_for_retry - now).total_seconds()))

                else: # Non-rolling intervals
                    # query_end_time is already calculated as the actual end of the fixed period
                    retry_after_seconds = max(0, int((query_end_time - now).total_seconds()))

                return False, reason_message, retry_after_seconds
        return True, None, None

    def _get_period_start(self, current_time: datetime, interval_unit: TimeInterval, interval_value: int) -> datetime:
        # Ensure current_time is UTC-aware for consistent calculations
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Truncate current_time to second precision for consistent rolling window calculations
        current_time_truncated = current_time.replace(microsecond=0)
        # No need to adjust current_time_truncated here, it's just for calculating period_start

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
            if interval_value != 1:
                pass
            start_of_current_day = current_time_truncated.replace(hour=0, minute=0, second=0, microsecond=0)
            # Ensure both datetimes are UTC-aware for subtraction
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
                # Ensure both datetimes are UTC-aware for subtraction
                epoch_week_start = datetime(1970, 1, 5, tzinfo=timezone.utc)
                weeks_since_epoch = (start_of_current_iso_week - epoch_week_start).days // 7
                weeks_offset = weeks_since_epoch % interval_value
                period_start = start_of_current_iso_week - timedelta(weeks=weeks_offset)
        elif interval_unit == TimeInterval.MONTH:
            year = current_time_truncated.year
            month = current_time_truncated.month
            total_months_current = year * 12 + month -1
            months_offset = total_months_current % interval_value
            effective_total_months = total_months_current - months_offset
            effective_year = effective_total_months // 12
            effective_month = (effective_total_months % 12) + 1
            period_start = current_time_truncated.replace(year=effective_year, month=effective_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif interval_unit == TimeInterval.SECOND_ROLLING:
            period_start = (current_time_truncated - timedelta(seconds=interval_value))
        elif interval_unit == TimeInterval.MINUTE_ROLLING:
            period_start = (current_time_truncated - timedelta(minutes=interval_value))
        elif interval_unit == TimeInterval.HOUR_ROLLING:
            period_start = (current_time_truncated - timedelta(hours=interval_value))
        elif interval_unit == TimeInterval.DAY_ROLLING:
            period_start = (current_time_truncated - timedelta(days=interval_value))
        elif interval_unit == TimeInterval.WEEK_ROLLING:
            period_start = (current_time_truncated - timedelta(weeks=interval_value))
        elif interval_unit == TimeInterval.MONTH_ROLLING:
            # Calculate month rolling window precisely
            year = current_time_truncated.year
            month = current_time_truncated.month
            
            # Calculate target month and year
            target_month = month - interval_value
            target_year = year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            
            period_start = current_time_truncated.replace(year=target_year, month=target_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported time interval unit: {interval_unit}")
        return period_start

    # The _is_rolling_interval method is no longer needed here as the logic is moved to TimeInterval enum.
