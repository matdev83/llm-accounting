import logging
from typing import Optional, Tuple, Dict, List
from datetime import datetime, timezone # Import datetime and timezone

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
        # Cache for storing recent denials and their retry-after timestamps
        # Key: tuple of (model, username, caller_name, project_name)
        # Value: tuple of (reason_message, reset_timestamp_utc)
        self._denial_cache: Dict[Tuple[Optional[str], Optional[str], Optional[str], Optional[str]], Tuple[str, datetime]] = {}
        self._denial_cache = {} # Ensure it's empty on initialization
        logger.info(f"QuotaService initialized. _denial_cache is empty: {not bool(self._denial_cache)}")

    def refresh_limits_cache(self) -> None:
        """Refreshes the limits cache from the backend and clears the denial cache."""
        self.cache_manager.refresh_limits_cache()
        self._denial_cache.clear() # Clear the denial cache
        logger.info("Denial cache cleared due to limits cache refresh.")

    def refresh_projects_cache(self) -> None:
        """Refreshes the projects cache from the backend."""
        self.cache_manager.refresh_projects_cache()

    def insert_limit(self, limit: UsageLimitDTO) -> None:
        """Inserts a new usage limit and refreshes the cache."""
        self.backend.insert_usage_limit(limit)
        self.refresh_limits_cache() # Use the existing refresh_limits_cache method

    def delete_limit(self, limit_id: int) -> None:
        """Deletes a usage limit and refreshes the cache."""
        self.backend.delete_usage_limit(limit_id)
        self.refresh_limits_cache() # Use the existing refresh_limits_cache method

    # --- Project management ---

    def create_project(self, name: str) -> None:
        self.backend.create_project(name)
        self.refresh_projects_cache()

    def list_projects(self) -> List[str]:
        if self.cache_manager.projects_cache is None:
            self.cache_manager._load_projects_from_backend()
        return self.cache_manager.projects_cache

    def update_project(self, name: str, new_name: str) -> None:
        self.backend.update_project(name, new_name)
        self.refresh_projects_cache()

    def delete_project(self, name: str) -> None:
        self.backend.delete_project(name)
        self.refresh_projects_cache()

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
        # Delegate to the enhanced check and discard the retry_after value
        allowed, reason, _ = self.check_quota_enhanced(
            model, username, caller_name, input_tokens, cost, completion_tokens, project_name
        )
        return allowed, reason

    def get_remaining_limits(
        self,
        model: Optional[str],
        username: Optional[str],
        caller_name: Optional[str],
        project_name: Optional[str],
    ) -> List[Tuple[UsageLimitDTO, float]]:
        """Return remaining quota for all limits applicable to the request."""
        if self.cache_manager.limits_cache is None:
            self.cache_manager._load_limits_from_backend()

        remaining_info: List[Tuple[UsageLimitDTO, float]] = []
        for limit in self.cache_manager.limits_cache:
            remaining = self.limit_evaluator.calculate_remaining_after_usage(
                limit, model, username, caller_name, project_name
            )
            if remaining is not None:
                remaining_info.append((limit, remaining))
        return remaining_info

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
        """Check quota with caching and retry-after handling.

        If a previous request for the same combination of parameters was denied
        with a ``retry_after`` timestamp, that denial is cached in
        ``self._denial_cache``. Subsequent requests hit the cache and return the
        cached denial until the stored timestamp expires. The cache therefore
        acts as a TTL store keyed by ``(model, username, caller_name,
        project_name)`` so we avoid redundant backend queries while the caller
        must wait anyway.
        """
        # Generate a cache key from the request parameters
        cache_key = (model, username, caller_name, project_name)
        now = datetime.now(timezone.utc)

        # 1. Check cache first
        if cache_key in self._denial_cache:
            cached_reason, cached_reset_timestamp = self._denial_cache[cache_key]
            
            # Calculate remaining retry_after time
            remaining_seconds = max(0, int((cached_reset_timestamp - now).total_seconds()))
            
            if remaining_seconds > 0:
                # Cache hit and still valid, return cached denial
                return False, cached_reason, remaining_seconds
            else:
                # Cache expired, remove it. Then, proceed to re-evaluate limits.
                del self._denial_cache[cache_key]
                # Continue to re-evaluate limits after cache expiration

        # Ensure cache is loaded before starting checks
        if self.cache_manager.limits_cache is None:
            self.cache_manager._load_limits_from_backend()

        # Pass all limits from the cache to the evaluator, which handles filtering
        all_applicable_limits = sorted(
            self.cache_manager.limits_cache,
            key=lambda l: sum(
                1
                for v in [l.model, l.username, l.caller_name, l.project_name]
                if v in (None, "*")
            ),
        )

        # Evaluate all collected limits at once
        allowed, reason, reset_timestamp = self.limit_evaluator._evaluate_limits_enhanced(
            all_applicable_limits, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )

        if not allowed:
            if reset_timestamp:
                self._denial_cache[cache_key] = (reason, reset_timestamp)
                retry_after_seconds = max(0, int((reset_timestamp - now).total_seconds()))
            else:
                retry_after_seconds = 0
            return False, reason, retry_after_seconds
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
            limit for limit in self.cache_manager.limits_cache if
            LimitScope(limit.scope) == LimitScope.GLOBAL
        ]
        return self.limit_evaluator._evaluate_limits_enhanced(
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
            limit
            for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.MODEL
            and (
                limit.model == model
                or limit.model == "*"
                or limit.model is None
            )
        ]
        limits_to_evaluate.sort(
            key=lambda l: 1 if l.model in (None, "*") else 0
        )
        return self.limit_evaluator._evaluate_limits_enhanced(limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens)

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
            limit
            for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.PROJECT
            and (
                (limit.project_name == project_name)
                or limit.project_name == "*"
                or (limit.project_name is None and project_name is None)
            )
        ]
        limits_to_evaluate.sort(
            key=lambda l: 1 if l.project_name in (None, "*") else 0
        )
        return self.limit_evaluator._evaluate_limits_enhanced(limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens)

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
            limit
            for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.USER
            and (
                limit.username == username
                or limit.username == "*"
                or limit.username is None
            )
        ]
        limits_to_evaluate.sort(
            key=lambda l: 1 if l.username in (None, "*") else 0
        )
        return self.limit_evaluator._evaluate_limits_enhanced(
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
            limit
            for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER
            and (
                limit.caller_name == caller_name
                or limit.caller_name == "*"
                or limit.caller_name is None
            )
            and limit.username is None
        ]
        limits_to_evaluate.sort(
            key=lambda l: 1 if l.caller_name in (None, "*") else 0
        )
        return self.limit_evaluator._evaluate_limits_enhanced(
            limits_to_evaluate,
            model,
            username,
            caller_name,
            project_name,
            input_tokens,
            cost,
            completion_tokens,
            limit_scope_for_message=f"CALLER (caller: {caller_name})",
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
            limit
            for limit in self.cache_manager.limits_cache
            if LimitScope(limit.scope) == LimitScope.CALLER
            and (
                limit.username == username
                or limit.username == "*"
                or limit.username is None
            )
            and (
                limit.caller_name == caller_name
                or limit.caller_name == "*"
                or limit.caller_name is None
            )
        ]
        limits_to_evaluate.sort(
            key=lambda l: (
                1 if l.username in (None, "*") else 0,
                1 if l.caller_name in (None, "*") else 0,
            )
        )
        return self.limit_evaluator._evaluate_limits_enhanced(
            limits_to_evaluate, model, username, caller_name, project_name, input_tokens, cost, completion_tokens
        )
