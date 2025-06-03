import logging
import sys # Import sys for direct print to stderr
from typing import Optional, Tuple, List, Any

from ..backends.base import BaseBackend
from ..models.limits import LimitScope, UsageLimitDTO

from .quota_service_parts._cache_manager import QuotaServiceCacheManager
from .quota_service_parts._limit_evaluator import QuotaServiceLimitEvaluator

logger = logging.getLogger(__name__)


class QuotaService:
    def __init__(self, backend: BaseBackend):
        self.backend = backend
        self.cache_manager = QuotaServiceCacheManager(backend)
        self.limit_evaluator = QuotaServiceLimitEvaluator(backend)

    def refresh_limits_cache(self) -> None:
        """Refreshes the limits cache from the backend."""
        self.cache_manager.refresh_limits_cache()

    def check_quota(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int = 0,
        project_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        # Ensure cache is loaded before starting checks
        if self.cache_manager.limits_cache is None:
            self.cache_manager._load_limits_from_backend()

        checks = [
            self._check_global_limits,
            self._check_model_limits,
            self._check_project_limits,
            self._check_user_limits,
            self._check_caller_limits,
            self._check_user_caller_limits,
        ]

        for check_func in checks:
            allowed, reason = check_func(
                model, username, caller_name, input_tokens, cost, completion_tokens, project_name
            )
            if not allowed:
                return False, reason
        return True, None

    def _check_global_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.GLOBAL
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )

    # --- Enhanced Check Methods ---

    def check_quota_enhanced(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int = 0,
        project_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        # Ensure cache is loaded before starting checks
        if self.cache_manager.limits_cache is None:
            self.cache_manager._load_limits_from_backend()

        enhanced_checks = [
            self._check_global_limits_enhanced,
            self._check_model_limits_enhanced,
            self._check_project_limits_enhanced,
            self._check_user_limits_enhanced,
            self._check_caller_limits_enhanced,
            self._check_user_caller_limits_enhanced,
        ]

        for check_func in enhanced_checks:
            allowed, reason, retry_after = check_func(
                model, username, caller_name, input_tokens, cost, completion_tokens, project_name
            )
            if not allowed:
                return False, reason, retry_after
        return True, None, None

    def _check_global_limits_enhanced(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.GLOBAL
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )

    def _check_model_limits_enhanced(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        if not model:
            return True, None, None

        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.MODEL and limit.model == model
        ]
        return self.limit_evaluator._evaluate_limits(limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens)

    def _check_project_limits_enhanced(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        if not project_name:
            return True, None, None

        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.PROJECT and limit.project_name == project_name
        ]
        return self.limit_evaluator._evaluate_limits(limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens)

    def _check_user_limits_enhanced(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        if not username:
             return True, None, None

        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.USER and limit.username == username
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )

    def _check_caller_limits_enhanced(
        self,
        model: Optional[str],
        username: Optional[str], # This username is for the request, not the limit's username field here.
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        if not caller_name:
            return True, None, None

        # For CALLER scope limits that are *not* specific to a user (i.e., limit.username is None)
        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER
            and limit.caller_name == caller_name
            and limit.username is None # Explicitly for generic caller limits
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens, limit_scope_for_message="CALLER (caller: {caller_name})"
        )

    def _check_user_caller_limits_enhanced(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        if not username or not caller_name:
            return True, None, None

        # For CALLER scope limits that *are* specific to a user (limit.username is not None)
        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER # Scope is still CALLER
            and limit.username == username
            and limit.caller_name == caller_name
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )

    def _check_model_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not model:
            return True, None

        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.MODEL and limit.model == model
        ]
        return self.limit_evaluator._evaluate_limits(limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens)

    def _check_project_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not project_name:
            return True, None

        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.PROJECT and limit.project_name == project_name
        ]
        return self.limit_evaluator._evaluate_limits(limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens)


    def _check_user_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not username:
             return True, None

        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.USER and limit.username == username
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )

    def _check_caller_limits(
        self,
        model: Optional[str],
        username: Optional[str], # This username is for the request, not the limit's username field here.
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not caller_name:
            return True, None

        # For CALLER scope limits that are *not* specific to a user (i.e., limit.username is None)
        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER
            and limit.caller_name == caller_name
            and limit.username is None # Explicitly for generic caller limits
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens, limit_scope_for_message="CALLER (caller: {caller_name})"
        )

    def _check_user_caller_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        input_tokens: int,
        cost: float,
        completion_tokens: int,
        project_name: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        if not username or not caller_name:
            return True, None

        # For CALLER scope limits that *are* specific to a user (limit.username is not None)
        limits_to_evaluate = [
            limit for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER # Scope is still CALLER
            and limit.username == username
            and limit.caller_name == caller_name
        ]
        return self.limit_evaluator._evaluate_limits(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )
