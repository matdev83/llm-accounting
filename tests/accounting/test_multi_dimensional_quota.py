import pytest
from datetime import datetime, timezone, timedelta
from freezegun import freeze_time

from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from llm_accounting.backends.base import BaseBackend
from llm_accounting.services.quota_service import QuotaService


@pytest.fixture
def sqlite_backend_for_accounting(temp_db_path):
    backend = SQLiteBackend(db_path=temp_db_path)
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def accounting_instance(sqlite_backend_for_accounting):
    acc = LLMAccounting(backend=sqlite_backend_for_accounting)
    acc.__enter__()
    yield acc
    acc.__exit__(None, None, None)

@freeze_time("2024-01-01 00:00:00", tz_offset=0)
def test_global_limit_overrides_user_limit(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value,
        limit_type=LimitType.REQUESTS.value,
        max_value=3,
        interval_unit=TimeInterval.SECOND_ROLLING.value,
        interval_value=10,
    )
    user_limit = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username="user1",
        limit_type=LimitType.REQUESTS.value,
        max_value=10,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1,
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)
    sqlite_backend_for_accounting.insert_usage_limit(user_limit)

    accounting_instance.quota_service.refresh_limits_cache()

    with freeze_time("2024-01-01 00:00:05", tz_offset=0) as freezer:
        for i in range(3):
            freezer.tick(delta=timedelta(seconds=1))
            accounting_instance.track_usage(
                model="gpt-4",
                username=f"u{i}",
                caller_name="app",
                prompt_tokens=1,
                completion_tokens=1,
                cost=0.0,
                timestamp=datetime.now(timezone.utc),
            )

        allowed, message = accounting_instance.check_quota(
            "gpt-4", "user1", "app", 1, 0.0
        )
        assert not allowed
        assert message is not None
        assert "GLOBAL limit" in message
        assert "10 second_rolling" in message


@freeze_time("2024-01-01 00:00:00", tz_offset=0)
def test_user_limit_triggered_before_global(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    global_limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value,
        limit_type=LimitType.REQUESTS.value,
        max_value=10,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1,
    )
    user_limit = UsageLimitDTO(
        scope=LimitScope.USER.value,
        username="user1",
        limit_type=LimitType.REQUESTS.value,
        max_value=2,
        interval_unit=TimeInterval.MINUTE_ROLLING.value,
        interval_value=1,
    )
    sqlite_backend_for_accounting.insert_usage_limit(global_limit)
    sqlite_backend_for_accounting.insert_usage_limit(user_limit)

    accounting_instance.quota_service.refresh_limits_cache()

    with freeze_time("2024-01-01 00:00:30", tz_offset=0) as freezer:
        for _ in range(2):
            freezer.tick(delta=timedelta(seconds=1))
            accounting_instance.track_usage(
                model="gpt-4",
                username="user1",
                caller_name="app",
                prompt_tokens=1,
                completion_tokens=1,
                cost=0.0,
                timestamp=datetime.now(timezone.utc),
            )
        for _ in range(5):
            freezer.tick(delta=timedelta(seconds=1))
            accounting_instance.track_usage(
                model="gpt-4",
                username="other",
                caller_name="app",
                prompt_tokens=1,
                completion_tokens=1,
                cost=0.0,
                timestamp=datetime.now(timezone.utc),
            )

        allowed, message = accounting_instance.check_quota(
            "gpt-4", "user1", "app", 1, 0.0
        )
        assert not allowed
        assert message is not None
        assert "USER (user: user1)" in message
        assert "minute_rolling" in message


@freeze_time("2024-01-01 00:10:00", tz_offset=0)
def test_model_and_project_limits_first_triggered(accounting_instance: LLMAccounting, sqlite_backend_for_accounting: SQLiteBackend):
    project_limit = UsageLimitDTO(
        scope=LimitScope.PROJECT.value,
        project_name="projA",
        limit_type=LimitType.COST.value,
        max_value=5.0,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1,
    )
    model_limit = UsageLimitDTO(
        scope=LimitScope.MODEL.value,
        model="gpt-4",
        limit_type=LimitType.INPUT_TOKENS.value,
        max_value=100,
        interval_unit=TimeInterval.MINUTE_ROLLING.value,
        interval_value=1,
    )
    sqlite_backend_for_accounting.insert_usage_limit(project_limit)
    sqlite_backend_for_accounting.insert_usage_limit(model_limit)

    accounting_instance.quota_service.refresh_limits_cache()

    accounting_instance.track_usage(
        model="gpt-4",
        username="user1",
        caller_name="app",
        prompt_tokens=10,
        completion_tokens=10,
        cost=5.0,
        project="projA",
        timestamp=datetime(2024, 1, 1, 0, 9, 0, tzinfo=timezone.utc),
    )
    for _ in range(3):
        accounting_instance.track_usage(
            model="gpt-4",
            username="user1",
            caller_name="app",
            prompt_tokens=20,
            completion_tokens=0,
            cost=0.0,
            project="projA",
            timestamp=datetime.now(timezone.utc),
        )

    allowed, message = accounting_instance.check_quota(
        "gpt-4", "user1", "app", 50, 1.0, project_name="projA"
    )
    assert not allowed
    assert message is not None
    assert ("MODEL (model: gpt-4)" in message) or ("PROJECT (project: projA)" in message)

@freeze_time("2024-01-01 00:00:40", tz_offset=0)
def test_denial_cache_ttl_behavior():
    from unittest.mock import MagicMock
    mock_backend = MagicMock(spec=BaseBackend)

    limit = UsageLimitDTO(
        scope=LimitScope.GLOBAL.value,
        limit_type=LimitType.REQUESTS.value,
        max_value=1,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1,
    )
    mock_backend.get_usage_limits.return_value = [limit]
    mock_backend.get_accounting_entries_for_quota.return_value = 1.0

    quota_service = QuotaService(mock_backend)
    quota_service.refresh_limits_cache()

    allowed, reason, retry_after = quota_service.check_quota_enhanced(
        model="gpt-4", username="u", caller_name="app", input_tokens=1, cost=0.0
    )
    assert not allowed
    assert retry_after == 20
    assert (("gpt-4", "u", "app", None) in quota_service._denial_cache)
    assert mock_backend.get_accounting_entries_for_quota.call_count == 1

    mock_backend.get_accounting_entries_for_quota.reset_mock()
    allowed2, reason2, retry_after2 = quota_service.check_quota_enhanced(
        model="gpt-4", username="u", caller_name="app", input_tokens=1, cost=0.0
    )
    assert not allowed2
    assert retry_after2 == 20
    mock_backend.get_accounting_entries_for_quota.assert_not_called()

    mock_backend.get_accounting_entries_for_quota.reset_mock()
    mock_backend.get_accounting_entries_for_quota.return_value = 0.0
    with freeze_time("2024-01-01 00:01:01", tz_offset=0):
        allowed3, reason3, retry_after3 = quota_service.check_quota_enhanced(
            model="gpt-4", username="u", caller_name="app", input_tokens=1, cost=0.0
        )
        assert allowed3
        assert reason3 is None
        assert retry_after3 is None
        assert mock_backend.get_accounting_entries_for_quota.call_count == 1
        assert ("gpt-4", "u", "app", None) not in quota_service._denial_cache
