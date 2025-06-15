from typing import Optional, List
from ...backends.base import TransactionalBackend
from ...models.limits import UsageLimitDTO


class QuotaServiceCacheManager:
    def __init__(self, backend: TransactionalBackend):
        self.backend = backend
        self.limits_cache: Optional[List[UsageLimitDTO]] = None
        self.projects_cache: Optional[List[str]] = None
        self.users_cache: Optional[List[str]] = None
        self._load_limits_from_backend()
        self._load_projects_from_backend()
        self._load_users_from_backend()

    def _load_limits_from_backend(self) -> None:
        """Loads all usage limits from the backend into the cache."""
        self.limits_cache = self.backend.get_usage_limits()

    def _load_projects_from_backend(self) -> None:
        """Loads allowed project names from the backend."""
        self.projects_cache = self.backend.list_projects()

    def _load_users_from_backend(self) -> None:
        """Loads allowed user names from the backend."""
        if hasattr(self.backend, "list_users"):
            # Removed try-except TypeError to let potential errors propagate
            self.users_cache = [u.user_name for u in self.backend.list_users()]
        else:
            self.users_cache = []

    def refresh_limits_cache(self) -> None:
        """Refreshes the limits cache from the backend."""
        self.limits_cache = None
        self._load_limits_from_backend()

    def refresh_projects_cache(self) -> None:
        """Refreshes the project name cache from the backend."""
        self.projects_cache = None
        self._load_projects_from_backend()

    def refresh_users_cache(self) -> None:
        """Refreshes the user name cache from the backend."""
        self.users_cache = None
        self._load_users_from_backend()
