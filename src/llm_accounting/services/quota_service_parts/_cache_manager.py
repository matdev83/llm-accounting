from typing import Optional, List
from ...backends.base import BaseBackend
from ...models.limits import UsageLimitDTO

class QuotaServiceCacheManager:
    def __init__(self, backend: BaseBackend):
        self.backend = backend
        self.limits_cache: Optional[List[UsageLimitDTO]] = None
        self._load_limits_from_backend()

    def _load_limits_from_backend(self) -> None:
        """Loads all usage limits from the backend into the cache."""
        self.limits_cache = self.backend.get_usage_limits()

    def refresh_limits_cache(self) -> None:
        """Refreshes the limits cache from the backend."""
        self.limits_cache = None
        self._load_limits_from_backend()
