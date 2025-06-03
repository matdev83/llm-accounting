import unittest
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

from freezegun import freeze_time

from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.base import Base
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from llm_accounting.models.accounting import AccountingEntry
from llm_accounting.services.quota_service import QuotaService
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


@freeze_time("2023-01-01 00:00:00", tz_offset=0)
class BaseTestRollingLimits(unittest.TestCase):
    def setUp(self):
        logging.getLogger('llm_accounting').setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.db_name_for_test = "memdb_test_rolling_limits"
        self.shared_in_memory_db_path = f"file:{self.db_name_for_test}?mode=memory&cache=shared"
        self.backend = SQLiteBackend(db_path=self.shared_in_memory_db_path)
        self.backend.initialize()

        TestSession = sessionmaker(bind=self.backend.connection_manager.engine)
        self.session = TestSession()

        self.quota_service = QuotaService(backend=self.backend)
        self.now = datetime.now(timezone.utc).replace(tzinfo=None) # Make it timezone-naive for consistency with SQLite
        
        self.backend.purge()
        self.quota_service.refresh_limits_cache()

    def tearDown(self):
        if self.session:
            self.session.close()
        if self.backend:
            self.backend.close()

    def _add_usage_limit(self, limit_dto: UsageLimitDTO):
        self.backend.insert_usage_limit(limit_dto)
        self.quota_service.refresh_limits_cache()

    def _add_accounting_entry(
        self,
        timestamp: datetime,
        model: str = "test-model",
        username: str = "test-user",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        project_name: Optional[str] = None,
        caller_name: Optional[str] = None,
        execution_time: float = 0.1,
    ):
        entry = AccountingEntry(
            timestamp=timestamp.replace(microsecond=0, tzinfo=None), # Ensure timezone-naive for SQLite
            model=model,
            username=username,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            cost=cost,
            project=project_name,
            caller_name=caller_name,
            execution_time=execution_time,
        )
        self.session.add(entry)
        self.session.commit()
        # Debugging: Verify the inserted entry
        # This will print the entry as it is in the session, not necessarily what's in DB
        # print(f"Added entry: {entry.timestamp}, {entry.project}, {entry.completion_tokens}")
