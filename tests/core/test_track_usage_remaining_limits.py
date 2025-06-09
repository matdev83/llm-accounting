import math
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval


def test_track_usage_with_remaining_limits(accounting):
    with accounting:
        accounting.set_usage_limit(
            scope=LimitScope.USER,
            limit_type=LimitType.TOTAL_TOKENS,
            max_value=100,
            interval_unit=TimeInterval.DAY,
            interval_value=1,
            username="alice",
        )
        accounting.set_usage_limit(
            scope=LimitScope.GLOBAL,
            limit_type=LimitType.COST,
            max_value=10,
            interval_unit=TimeInterval.DAY,
            interval_value=1,
        )
        accounting.quota_service.refresh_limits_cache()

        remaining = accounting.track_usage_with_remaining_limits(
            model="gpt-4",
            prompt_tokens=40,
            completion_tokens=10,
            total_tokens=50,
            cost=1.0,
            username="alice",
            caller_name="app",
        )

        results = {(lim.scope, lim.limit_type): rem for lim, rem in remaining}
        assert results[(LimitScope.USER.value, LimitType.TOTAL_TOKENS.value)] == 50.0
        assert results[(LimitScope.GLOBAL.value, LimitType.COST.value)] == 9.0


def test_track_usage_remaining_limits_special_values(accounting):
    with accounting:
        accounting.set_usage_limit(
            scope=LimitScope.MODEL,
            limit_type=LimitType.REQUESTS,
            model="*",
            max_value=0,
            interval_unit=TimeInterval.DAY,
            interval_value=1,
        )
        accounting.set_usage_limit(
            scope=LimitScope.MODEL,
            limit_type=LimitType.REQUESTS,
            model="gpt-4",
            max_value=-1,
            interval_unit=TimeInterval.DAY,
            interval_value=1,
        )
        accounting.quota_service.refresh_limits_cache()

        remaining = accounting.track_usage_with_remaining_limits(
            model="gpt-4",
            caller_name="app",
            username="alice",
        )

        results = {
            (lim.scope, lim.model, lim.limit_type): rem for lim, rem in remaining
        }
        assert results[(LimitScope.MODEL.value, "*", LimitType.REQUESTS.value)] == 0.0
        assert math.isinf(
            results[(LimitScope.MODEL.value, "gpt-4", LimitType.REQUESTS.value)]
        )
