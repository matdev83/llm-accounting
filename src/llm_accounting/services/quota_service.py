from datetime import datetime, timezone
from typing import Optional, Tuple

from ..backends.base import BaseBackend
from ..models.limits import LimitScope, LimitType


class QuotaService:
    def __init__(self, backend: BaseBackend):
        self.db = backend

    def check_quota(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float = 0.0,
    ) -> Tuple[bool, Optional[str]]:
        # Check limits in hierarchical order
        checks = [
            self._check_model_limits,
            self._check_global_limits,
            self._check_user_limits,
            self._check_caller_limits,
            self._check_user_caller_limits,
        ]

        for check in checks:
            allowed, message = check(model, username, caller_name, input_tokens, cost)
            if not allowed:
                return False, message

        return True, None

    def _check_global_limits(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.db.get_usage_limits(scope=LimitScope.GLOBAL)
        return self._evaluate_limits(
            limits, model, username, caller_name, input_tokens, cost
        )

    def _check_model_limits(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.db.get_usage_limits(scope=LimitScope.MODEL, model=model)
        return self._evaluate_limits(limits, model, None, None, input_tokens, cost)

    def _check_user_limits(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.db.get_usage_limits(scope=LimitScope.USER, username=username)
        return self._evaluate_limits(
            limits, model, username, caller_name, input_tokens, cost
        )

    def _check_caller_limits(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.db.get_usage_limits(
            scope=LimitScope.CALLER, caller_name=caller_name
        )
        return self._evaluate_limits(
            limits, model, username, caller_name, input_tokens, cost
        )

    def _check_user_caller_limits(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        cost: float,
    ) -> Tuple[bool, Optional[str]]:
        limits = self.db.get_usage_limits(
            scope=LimitScope.CALLER, username=username, caller_name=caller_name
        )
        return self._evaluate_limits(
            limits, model, username, caller_name, input_tokens, cost
        )

    def _evaluate_limits(
        self, limits, model, username, caller_name, input_tokens, cost
    ):
        now = datetime.now(timezone.utc)
        for limit in limits:
            start_time = now - limit.time_delta()

            current_usage = self._get_usage(
                limit.limit_type,
                start_time,
                model=model,
                username=username,
                caller_name=caller_name,
            )

            if limit.limit_type == LimitType.REQUESTS.value:
                potential_usage = current_usage + 1
            elif limit.limit_type == LimitType.INPUT_TOKENS.value:
                potential_usage = current_usage + input_tokens
            elif limit.limit_type == LimitType.COST.value:
                potential_usage = current_usage + cost
            else:
                raise ValueError(
                    f"Unknown limit type encountered in _evaluate_limits: {limit.limit_type}"
                )

            if potential_usage > limit.max_value:
                formatted_max = f"{float(limit.max_value):.2f}"
                return (
                    False,
                    f"{limit.scope.upper()} limit: {formatted_max} {limit.limit_type} per {limit.interval_value} {limit.interval_unit}",
                )

        return True, None

    def _get_usage(
        self,
        limit_type: str,
        start_time: datetime,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
    ) -> float:
        return self.db.get_api_requests_for_quota(
            start_time=start_time,
            limit_type=LimitType(limit_type),
            model=model,
            username=username,
            caller_name=caller_name,
        )
