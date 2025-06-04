import logging
import sys # Import sys for direct print to stderr
from typing import Optional, Tuple, List, Any, Dict # Import Dict
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
        # Delegate to the enhanced check and discard the retry_after value
        allowed, reason, _ = self.check_quota_enhanced(
            model, username, caller_name, input_tokens, cost, completion_tokens, project_name
        )
        return allowed, reason

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
        all_applicable_limits = self.cache_manager.limits_cache

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
