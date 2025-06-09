import pytest
from datetime import datetime, timezone
from freezegun import freeze_time

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import (
    UsageLimitDTO,
    LimitScope,
    LimitType,
    TimeInterval,
)


@pytest.fixture
def sqlite_backend_for_accounting(temp_db_path):
    backend = SQLiteBackend(db_path=temp_db_path)
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def accounting_instance(sqlite_backend_for_accounting: SQLiteBackend) -> LLMAccounting:
    acc = LLMAccounting(backend=sqlite_backend_for_accounting)
    acc.__enter__()
    yield acc
    acc.__exit__(None, None, None)


@freeze_time("2024-01-01 00:00:00", tz_offset=0)
def test_wildcard_deny_and_specific_allow(
    accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend
):
    deny_all = UsageLimitDTO(
        scope=LimitScope.MODEL.value,
        model="*",
        limit_type=LimitType.REQUESTS.value,
        max_value=0,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
    )
    allow_gpt4 = UsageLimitDTO(
        scope=LimitScope.MODEL.value,
        model="gpt-4",
        limit_type=LimitType.REQUESTS.value,
        max_value=-1,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
    )
    sqlite_backend_for_accounting.insert_usage_limit(deny_all)
    sqlite_backend_for_accounting.insert_usage_limit(allow_gpt4)
    accounting_instance.quota_service.refresh_limits_cache()

    allowed, _ = accounting_instance.check_quota("gpt-4", None, "app", 1, 0)
    assert allowed

    allowed, _ = accounting_instance.check_quota("gpt-3", None, "app", 1, 0)
    assert not allowed


@freeze_time("2024-01-01 00:00:00", tz_offset=0)
def test_unlimited_limit(
    accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend
):
    unlimited = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username="user1",
        limit_type=LimitType.COST.value,
        max_value=-1,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
    )
    sqlite_backend_for_accounting.insert_usage_limit(unlimited)
    accounting_instance.quota_service.refresh_limits_cache()

    for _ in range(5):
        allowed, _ = accounting_instance.check_quota("gpt-4", "user1", "app", 1, 0.1)
        assert allowed


@freeze_time("2024-01-01 00:00:00", tz_offset=0)
def test_wildcard_user_deny_with_project_override(
    accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend
):
    """Deny all models for a user, allow specific models and project overrides."""
    deny_all = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username="alice",
        model="*",
        limit_type=LimitType.REQUESTS.value,
        max_value=0,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
    )
    allow_gpt4 = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username="alice",
        model="gpt-4",
        limit_type=LimitType.REQUESTS.value,
        max_value=-1,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
    )
    allow_project_model = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username="alice",
        model="gpt-3.5",
        project_name="ProjectX",
        limit_type=LimitType.REQUESTS.value,
        max_value=-1,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
    )
    sqlite_backend_for_accounting.insert_usage_limit(deny_all)
    sqlite_backend_for_accounting.insert_usage_limit(allow_gpt4)
    sqlite_backend_for_accounting.insert_usage_limit(allow_project_model)
    accounting_instance.quota_service.refresh_limits_cache()

    allowed, _ = accounting_instance.check_quota("gpt-4", "alice", "client", 1, 0)
    assert allowed
    allowed, _ = accounting_instance.check_quota(
        "gpt-4", "alice", "client", 1, 0, project_name="ProjectX"
    )
    assert allowed
    allowed, _ = accounting_instance.check_quota("gpt-3.5", "alice", "client", 1, 0)
    assert not allowed
    allowed, _ = accounting_instance.check_quota(
        "gpt-3.5", "alice", "client", 1, 0, project_name="ProjectX"
    )
    assert allowed
