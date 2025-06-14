from typing import Optional, List
from ...backends.base import BaseBackend
from ...models.limits import UsageLimitDTO

class QuotaServiceCacheManager:
    def __init__(self, backend: BaseBackend):
        self.backend = backend
        self.limits_cache: Optional[List[UsageLimitDTO]] = None
        self.projects_cache: Optional[List[str]] = None
        self._load_limits_from_backend()
        self._load_projects_from_backend()

    def _load_limits_from_backend(self) -> None:
        """Loads all usage limits from the backend into the cache."""
        self.limits_cache = self.backend.get_usage_limits()

    def _load_projects_from_backend(self) -> None:
        """Loads allowed project names from the backend."""
        self.projects_cache = self.backend.list_projects()

    def refresh_limits_cache(self) -> None:
        """Refreshes the limits cache from the backend."""
        self.limits_cache = None
        self._load_limits_from_backend()

    def refresh_projects_cache(self) -> None:
        """Refreshes the project name cache from the backend."""
        self.projects_cache = None
        self._load_projects_from_backend()
