import logging  # Added logging import
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

from ...backends.base import TransactionalBackend
from ...models.limits import LimitType, TimeInterval, UsageLimitDTO, LimitScope

logger = logging.getLogger(__name__)


class QuotaServiceLimitEvaluator:
    def __init__(self, backend: TransactionalBackend):
        self.backend = backend

    def _prepare_usage_query_params(self, limit: UsageLimitDTO, limit_scope_enum: LimitScope) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[bool]]:
        final_usage_query_model: Optional[str] = None
        final_usage_query_username: Optional[str] = None
        final_usage_query_caller_name: Optional[str] = None
        final_usage_query_project_name: Optional[str] = None
        final_usage_query_filter_project_null: Optional[bool] = None

        if limit_scope_enum != LimitScope.GLOBAL:
            if limit.model is not None and limit.model != "*":
                final_usage_query_model = limit.model
            if limit.username is not None and limit.username != "*":
                final_usage_query_username = limit.username
            if limit.caller_name is not None and limit.caller_name != "*":
                final_usage_query_caller_name = limit.caller_name

            if limit.project_name is not None and limit.project_name != "*":
                final_usage_query_project_name = limit.project_name
            elif limit_scope_enum == LimitScope.PROJECT and limit.project_name is None:
                # Only filter for NULL project if the limit is specifically a PROJECT scope limit with no project_name
                final_usage_query_filter_project_null = True
            # If it's not a PROJECT scope limit, but project_name is None on the limit,
            # it means this limit applies regardless of the request's project (unless project_name is specified on limit).
            # If project_name is '*' on the limit, it also applies regardless of request's project.
            # These cases are implicitly handled by not setting final_usage_query_project_name,
            # thus not filtering by project in the consuming query.

        return (final_usage_query_model, final_usage_query_username, final_usage_query_caller_name,
                final_usage_query_project_name, final_usage_query_filter_project_null)

    def _calculate_request_value(self, limit_type_enum: LimitType, request_input_tokens: int,
                                 request_completion_tokens: int, request_cost: float) -> Optional[float]:
        if limit_type_enum == LimitType.REQUESTS:
            return 1.0
        elif limit_type_enum == LimitType.INPUT_TOKENS:
            return float(request_input_tokens)
        elif limit_type_enum == LimitType.OUTPUT_TOKENS:
            return float(request_completion_tokens)
        elif limit_type_enum == LimitType.TOTAL_TOKENS:
            return float(request_input_tokens + request_completion_tokens)
        elif limit_type_enum == LimitType.COST:
            return request_cost
        else:
            return None

    def _format_exceeded_reason_message(self, limit: UsageLimitDTO,
                                        limit_scope_for_message: Optional[str],
                                        current_usage: float, request_value: float) -> str:
        if limit_scope_for_message:
            scope_msg_str = limit_scope_for_message
        else:
            scope_details_map = {
                LimitScope.USER.value: f"USER (user: {limit.username})" if limit.username else "USER",
                LimitScope.MODEL.value: f"MODEL (model: {limit.model})" if limit.model else "MODEL",
                LimitScope.CALLER.value: f"CALLER (user: {limit.username}, caller: {limit.caller_name})" if limit.username and limit.caller_name else (f"CALLER (caller: {limit.caller_name})" if limit.caller_name else "CALLER"),
                LimitScope.PROJECT.value: f"PROJECT (project: {limit.project_name})" if limit.project_name else "PROJECT (no project)",
            }
            scope_msg_str = scope_details_map.get(limit.scope, limit.scope)  # Defaults to raw scope string

        reason_message = (
            f"{scope_msg_str} limit: {limit.max_value:.2f} {limit.limit_type} per {limit.interval_value} {limit.interval_unit}"
            f" exceeded. Current usage: {current_usage:.2f}, request: {request_value:.2f}."
        )
        return reason_message

    def _should_skip_limit(self, limit: UsageLimitDTO, request_model: Optional[str],
                           request_username: Optional[str], request_caller_name: Optional[str],
                           project_name_for_usage_sum: Optional[str]) -> bool:
        limit_scope_enum = LimitScope(limit.scope)
        if limit_scope_enum != LimitScope.GLOBAL:
            if limit.model and limit.model != "*" and limit.model != request_model:
                return True
            if limit.username and limit.username != "*" and limit.username != request_username:
                return True
            if limit.caller_name and limit.caller_name != "*" and limit.caller_name != request_caller_name:
                return True

            if limit.project_name:
                if limit.project_name != "*" and limit.project_name != project_name_for_usage_sum:
                    return True
            elif limit_scope_enum == LimitScope.PROJECT and limit.project_name is None:
                if project_name_for_usage_sum is not None:
                    return True
        return False  # Do not skip

    def _calculate_reset_timestamp(self, period_start_time: datetime,
                                   limit: UsageLimitDTO, interval_unit_enum: TimeInterval) -> datetime:
        _reset_timestamp: datetime
        if interval_unit_enum.is_rolling():
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
            _reset_timestamp = period_end_for_retry
        else:  # Non-rolling (fixed) intervals
            duration: timedelta
            if interval_unit_enum == TimeInterval.MONTH:
                start_year = period_start_time.year
                start_month = period_start_time.month
                next_period_raw_month = start_month + limit.interval_value
                next_period_year = start_year + (next_period_raw_month - 1) // 12
                next_period_month = (next_period_raw_month - 1) % 12 + 1
                _reset_timestamp = datetime(next_period_year, next_period_month, 1, 0, 0, 0, tzinfo=period_start_time.tzinfo)
            elif interval_unit_enum == TimeInterval.WEEK:
                duration = timedelta(weeks=limit.interval_value)
                _reset_timestamp = period_start_time + duration
            else:  # SECOND, MINUTE, HOUR, DAY
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
                _reset_timestamp = period_start_time + duration

        return _reset_timestamp.replace(microsecond=0)

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
            if self._should_skip_limit(limit, request_model, request_username, request_caller_name, project_name_for_usage_sum):
                continue

            if limit.max_value == -1:
                return True, None, None

            limit_scope_enum = LimitScope(limit.scope) # Define limit_scope_enum here
            interval_unit_enum = TimeInterval(limit.interval_unit) # Get enum member
            period_start_time = self._get_period_start(now, interval_unit_enum, limit.interval_value)

            reset_timestamp = self._calculate_reset_timestamp(period_start_time, limit, interval_unit_enum)

            (final_usage_query_model, final_usage_query_username, final_usage_query_caller_name,
             final_usage_query_project_name, final_usage_query_filter_project_null) = \
                self._prepare_usage_query_params(limit, limit_scope_enum)

            # Add logging here
            # import logging # Moved to top-level
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
            request_value_optional = self._calculate_request_value(limit_type_enum, request_input_tokens, request_completion_tokens, request_cost)
            if request_value_optional is None:
                logger.warning(f"Unknown or non-applicable limit type {limit_type_enum} for limit ID {limit.id if limit.id else 'N/A'}. Skipping.")
                continue
            request_value = request_value_optional

            potential_usage = current_usage + request_value

            # Convert to float for comparison, and round to avoid floating point inaccuracies
            # Using a precision of 6 decimal places should be sufficient for most cases.
            potential_usage_float = round(float(potential_usage), 6)
            limit_max_value_float = round(float(limit.max_value), 6)

            # Compare with a small epsilon to account for floating point inaccuracies
            comparison_result = potential_usage_float > limit_max_value_float

            if comparison_result:
                reason_message = self._format_exceeded_reason_message(limit, limit_scope_for_message, current_usage, request_value)
                return False, reason_message, reset_timestamp # Return reset_timestamp
        return True, None, None # Return None for reset_timestamp if allowed

    def calculate_remaining_after_usage(
        self,
        limit: UsageLimitDTO,
        request_model: Optional[str],
        request_username: Optional[str],
        request_caller_name: Optional[str],
        project_name_for_usage_sum: Optional[str],
        request_input_tokens: int = 0,
        request_completion_tokens: int = 0,
        request_cost: float = 0.0,
    ) -> Optional[float]:
        """Return remaining quota for ``limit`` considering current usage."""
        if self._should_skip_limit(
            limit,
            request_model,
            request_username,
            request_caller_name,
            project_name_for_usage_sum,
        ):
            return None

        if limit.max_value == -1:
            return float("inf")

        now = datetime.now(timezone.utc)
        limit_scope_enum = LimitScope(limit.scope)
        interval_unit_enum = TimeInterval(limit.interval_unit)
        period_start_time = self._get_period_start(now, interval_unit_enum, limit.interval_value)

        (
            final_usage_query_model,
            final_usage_query_username,
            final_usage_query_caller_name,
            final_usage_query_project_name,
            final_usage_query_filter_project_null,
        ) = self._prepare_usage_query_params(limit, limit_scope_enum)

        current_usage = self.backend.get_accounting_entries_for_quota(
            start_time=period_start_time,
            end_time=now,
            limit_type=LimitType(limit.limit_type),
            interval_unit=interval_unit_enum,
            model=final_usage_query_model,
            username=final_usage_query_username,
            caller_name=final_usage_query_caller_name,
            project_name=final_usage_query_project_name,
            filter_project_null=final_usage_query_filter_project_null,
        )

        # Calculate request value
        limit_type_enum = LimitType(limit.limit_type)
        request_value = self._calculate_request_value(
            limit_type_enum,
            request_input_tokens,
            request_completion_tokens,
            request_cost
        )
        if request_value is None:
            return None

        # Only subtract current usage from max value, since the current request hasn't been recorded yet
        remaining = float(limit.max_value) - current_usage
        return max(remaining, 0.0)

    def _get_period_start(self, current_time: datetime, interval_unit: TimeInterval, interval_value: int) -> datetime:
        # Ensure current_time is UTC-aware for consistent calculations
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Truncate current_time to second precision for consistent rolling window calculations
        current_time_truncated = current_time.replace(microsecond=0)

        # Fixed interval calculations
        if interval_unit == TimeInterval.SECOND:
            return current_time_truncated.replace(second=current_time_truncated.second - (current_time_truncated.second % interval_value), microsecond=0)
        if interval_unit == TimeInterval.MINUTE:
            return current_time_truncated.replace(minute=current_time_truncated.minute - (current_time_truncated.minute % interval_value), second=0, microsecond=0)
        if interval_unit == TimeInterval.HOUR:
            return current_time_truncated.replace(hour=current_time_truncated.hour - (current_time_truncated.hour % interval_value), minute=0, second=0, microsecond=0)
        if interval_unit == TimeInterval.DAY:
            start_of_current_day = current_time_truncated.replace(hour=0, minute=0, second=0, microsecond=0)
            epoch_start = datetime(1970, 1, 1, tzinfo=timezone.utc)
            days_since_epoch = (start_of_current_day - epoch_start).days
            days_offset = days_since_epoch % interval_value
            return start_of_current_day - timedelta(days=days_offset)
        if interval_unit == TimeInterval.WEEK:
            start_of_day = current_time_truncated.replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_current_iso_week = start_of_day - timedelta(days=start_of_day.weekday())
            if interval_value == 1:
                return start_of_current_iso_week
            epoch_week_start = datetime(1970, 1, 5, tzinfo=timezone.utc)  # A Monday
            weeks_since_epoch = (start_of_current_iso_week - epoch_week_start).days // 7
            weeks_offset = weeks_since_epoch % interval_value
            return start_of_current_iso_week - timedelta(weeks=weeks_offset)
        if interval_unit == TimeInterval.MONTH:
            year, month = current_time_truncated.year, current_time_truncated.month
            total_months_since_epoch = year * 12 + month - 1
            interval_start_month_index = (total_months_since_epoch // interval_value) * interval_value
            start_year, start_month = divmod(interval_start_month_index, 12)
            return current_time_truncated.replace(year=start_year, month=start_month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

        # Rolling interval calculations
        if interval_unit.is_rolling():
            delta_map = {
                TimeInterval.SECOND_ROLLING: timedelta(seconds=interval_value),
                TimeInterval.MINUTE_ROLLING: timedelta(minutes=interval_value),
                TimeInterval.HOUR_ROLLING: timedelta(hours=interval_value),
                TimeInterval.DAY_ROLLING: timedelta(days=interval_value),
                TimeInterval.WEEK_ROLLING: timedelta(weeks=interval_value),
            }
            if interval_unit == TimeInterval.MONTH_ROLLING:
                year, month = current_time_truncated.year, current_time_truncated.month
                target_month_val = month - interval_value
                target_year_val = year
                while target_month_val <= 0:
                    target_month_val += 12
                    target_year_val -= 1
                return current_time_truncated.replace(year=target_year_val, month=target_month_val, day=1, hour=0, minute=0, second=0, microsecond=0)
            if interval_unit in delta_map:
                return current_time_truncated - delta_map[interval_unit]
            raise ValueError(f"Unsupported rolling time interval unit in _get_period_start: {interval_unit}")

        raise ValueError(f"Unsupported time interval unit: {interval_unit}")
