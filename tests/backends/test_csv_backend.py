import pytest
import os
import csv
import shutil
from datetime import datetime, timedelta, timezone

from llm_accounting.backends.csv_backend import CSVBackend
from llm_accounting.backends.base import AuditLogEntry as BaseAuditLogEntry, UsageEntry as BaseUsageEntry, UsageStats as BaseUsageStats
from llm_accounting.models.limits import UsageLimitDTO as BaseUsageLimitDTO, LimitScope as BaseLimitScope, LimitType as BaseLimitType

# Aliases for the test file
AccountingEntry = BaseUsageEntry
PeriodStats = BaseUsageStats
UsageLimitDTO = BaseUsageLimitDTO
UsageLimitScope = BaseLimitScope
AuditLogEntry = BaseAuditLogEntry
# LimitType is available for tests that might use it for e.g. UsageLimitDTO
LimitType = BaseLimitType


# Helper function to get header of a csv file
def get_csv_header(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return []
    with open(file_path, 'r', newline='') as f:
        reader = csv.reader(f)
        return next(reader)

# Helper function to count data rows in a csv file (excluding header)
def count_csv_data_rows(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return 0
    with open(file_path, 'r', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None) # Skip header
        if not header:
            return 0
        return sum(1 for row in reader)


@pytest.fixture
def temp_data_dir(tmp_path):
    data_dir = tmp_path / "csv_data"
    data_dir.mkdir()
    yield str(data_dir)

@pytest.fixture
def csv_backend(temp_data_dir):
    backend = CSVBackend(csv_data_dir=temp_data_dir)
    backend.initialize()
    return backend

class TestCSVBackendInitialization:
    def test_initialization_default_dir(self, tmp_path):
        default_dir_mock = tmp_path / "default_data_dir"
        original_default_dir = CSVBackend.DEFAULT_DATA_DIR
        CSVBackend.DEFAULT_DATA_DIR = str(default_dir_mock)
        try:
            backend = CSVBackend()
            backend.initialize()
            assert os.path.exists(default_dir_mock)
            assert os.path.exists(os.path.join(default_dir_mock, CSVBackend.ACCOUNTING_ENTRIES_FILE))
        finally:
            CSVBackend.DEFAULT_DATA_DIR = original_default_dir

    def test_initialization_custom_dir(self, temp_data_dir):
        backend = CSVBackend(csv_data_dir=temp_data_dir)
        backend.initialize()
        assert os.path.exists(temp_data_dir)
        acc_file = os.path.join(temp_data_dir, CSVBackend.ACCOUNTING_ENTRIES_FILE)
        assert os.path.exists(acc_file)
        assert get_csv_header(acc_file) == CSVBackend.ACCOUNTING_FIELDNAMES

    def test_data_dir_creation(self, tmp_path):
        non_existent_dir = tmp_path / "new_csv_data"
        assert not os.path.exists(non_existent_dir)
        backend = CSVBackend(csv_data_dir=str(non_existent_dir))
        backend.initialize()
        assert os.path.exists(non_existent_dir)
        assert os.path.isdir(non_existent_dir)

    def test_initialization_existing_files(self, csv_backend, temp_data_dir):
        accounting_entry = AccountingEntry(model="gpt-4", total_tokens=100, timestamp=datetime.now(timezone.utc))
        csv_backend.insert_usage(accounting_entry) 
        assert count_csv_data_rows(csv_backend.accounting_file_path) == 1
        csv_backend.initialize() 
        assert count_csv_data_rows(csv_backend.accounting_file_path) == 1
        assert get_csv_header(csv_backend.accounting_file_path) == CSVBackend.ACCOUNTING_FIELDNAMES

class TestCSVPurge:
    def test_purge_clears_data_keeps_headers(self, csv_backend, temp_data_dir):
        now = datetime.now(timezone.utc)
        acc_entry = AccountingEntry(model="m1", total_tokens=10, timestamp=now)
        csv_backend.insert_usage(acc_entry)

        limit_entry = UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type="tokens", max_value=1000, interval_unit="month", interval_value=1, username="test_user")
        csv_backend.insert_usage_limit(limit_entry)
        
        audit_entry = AuditLogEntry(
            id=None, timestamp=now, app_name="test_app", user_name="tester", 
            model="test_model", log_type="info", prompt_text="test prompt", 
            response_text="test response", remote_completion_id="remote_test", project="test_project"
        )
        csv_backend.log_audit_event(audit_entry)

        assert count_csv_data_rows(csv_backend.accounting_file_path) == 1
        csv_backend.purge()
        assert count_csv_data_rows(csv_backend.accounting_file_path) == 0
        assert get_csv_header(csv_backend.accounting_file_path) == CSVBackend.ACCOUNTING_FIELDNAMES

class TestAccountingEntries:
    def test_insert_and_tail_single_entry(self, csv_backend):
        now = datetime.now(timezone.utc)
        # Added id=None to AccountingEntry instantiation for consistency
        entry = AccountingEntry(id=None, model="gpt-3.5-turbo", prompt_tokens=10, completion_tokens=20, total_tokens=30, cost=0.00015, timestamp=now, username="user1", project="projA")
        csv_backend.insert_usage(entry)
        tailed_entries = csv_backend.tail(n=1)
        assert len(tailed_entries) == 1
        retrieved = tailed_entries[0]
        assert retrieved.id == 1 
        assert retrieved.model == "gpt-3.5-turbo"

    def test_tail_multiple_entries_and_limit(self, csv_backend):
        now = datetime.now(timezone.utc)
        entry1 = AccountingEntry(id=None, model="m1", total_tokens=10, timestamp=now - timedelta(seconds=10), username="u1")
        entry2 = AccountingEntry(id=None, model="m2", total_tokens=20, timestamp=now - timedelta(seconds=5), username="u2")
        entry3 = AccountingEntry(id=None, model="m1", total_tokens=30, timestamp=now, username="u1", project="p1")
        csv_backend.insert_usage(entry1)
        csv_backend.insert_usage(entry2)
        csv_backend.insert_usage(entry3)
        tailed_2 = csv_backend.tail(n=2)
        assert len(tailed_2) == 2
        # Assuming tail returns newest first and IDs are sequential for insert order
        assert tailed_2[0].id == 2 
        assert tailed_2[1].id == 3
        assert tailed_2[0].total_tokens == 20 
        assert tailed_2[1].total_tokens == 30


    def test_tail_with_filters(self, csv_backend):
        now = datetime.now(timezone.utc)
        csv_backend.insert_usage(AccountingEntry(id=None, model="m1", total_tokens=10, timestamp=now, username="userA", project="projX"))
        csv_backend.insert_usage(AccountingEntry(id=None, model="m2", total_tokens=20, timestamp=now, username="userB", project="projY"))
        csv_backend.insert_usage(AccountingEntry(id=None, model="m1", total_tokens=30, timestamp=now, username="userA", project="projZ"))
        csv_backend.insert_usage(AccountingEntry(id=None, model="m3", total_tokens=40, timestamp=now, username="userC", project="projX"))
        tailed_userA = csv_backend.tail(n=5, username="userA")
        assert len(tailed_userA) == 2

    def test_insert_optional_fields_none_or_empty(self, csv_backend):
        now = datetime.now(timezone.utc)
        entry_none = AccountingEntry(id=None, model="test_model", total_tokens=5, timestamp=now, prompt_tokens=None, cost=None, username=None, project="")
        csv_backend.insert_usage(entry_none)
        retrieved_list = csv_backend.tail(n=1, model="test_model")
        assert len(retrieved_list) == 1
        retrieved = retrieved_list[0]
        assert retrieved.prompt_tokens == 0 
        assert retrieved.cost == 0.0 
        assert retrieved.username is None 
        assert retrieved.project is None

class TestUsageLimits:
    def test_insert_get_delete_usage_limit(self, csv_backend):
        limit1 = UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type="tokens", model="gpt-4", username="test_user", max_value=10000, interval_unit="month", interval_value=1)
        created_limit = csv_backend.insert_usage_limit(limit1)
        assert created_limit.id == 1 
        retrieved_limits = csv_backend.get_usage_limits(username="test_user")
        assert len(retrieved_limits) == 1
        assert retrieved_limits[0].id == 1
        csv_backend.delete_usage_limit(limit_id=1)
        retrieved_limits_after_delete = csv_backend.get_usage_limits(username="test_user")
        assert len(retrieved_limits_after_delete) == 0

    def test_get_usage_limits_various_filters(self, csv_backend):
        csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type="tokens", username="u1", model="m1", max_value=100, interval_unit="day", interval_value=1))
        csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type="cost", username="u1", model="m2", max_value=20, interval_unit="day", interval_value=1))
        csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.PROJECT, limit_type="tokens", project_name="p1", model="m1", max_value=1000, interval_unit="day", interval_value=1))
        csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.CALLER, limit_type="requests", caller_name="c1", max_value=50, interval_unit="day", interval_value=1))
        csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.GLOBAL, limit_type="tokens", model="m3", max_value=5000, interval_unit="day", interval_value=1))
        assert len(csv_backend.get_usage_limits(scope=UsageLimitScope.USER)) == 2
        csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type="tokens", username="u2", model=None, max_value=300, interval_unit="day", interval_value=1))
        u2_limits = csv_backend.get_usage_limits(username="u2")
        assert len(u2_limits) == 1

class TestAuditLog:
    def test_insert_get_audit_log_entry(self, csv_backend):
        now = datetime.now(timezone.utc)
        entry1 = AuditLogEntry(
            id=None, timestamp=now, app_name="App1", user_name="UserA", 
            model="ModelX", log_type="info", prompt_text="Hello", 
            response_text="Hi there", remote_completion_id="remote1", project="ProjectAlpha"
        )
        csv_backend.log_audit_event(entry1)
        
        retrieved_logs = csv_backend.get_audit_log_entries(limit=1)
        assert len(retrieved_logs) == 1
        retrieved = retrieved_logs[0]
        assert retrieved.id == 1
        assert retrieved.log_type == "info"

        entry2 = AuditLogEntry(
            id=None, timestamp=now + timedelta(seconds=10), app_name="App2", user_name="UserB", 
            model="ModelY", log_type="warning", prompt_text=None, 
            response_text=None, remote_completion_id="remote2", project="ProjectBeta"
        )
        csv_backend.log_audit_event(entry2)
        
        all_logs_newest_first = csv_backend.get_audit_log_entries(limit=2)
        assert all_logs_newest_first[0].id == 2 
        assert all_logs_newest_first[1].id == 1 

    def test_get_audit_log_entries_filters_and_pagination(self, csv_backend):
        t1 = datetime.now(timezone.utc) - timedelta(minutes=30)
        t2 = datetime.now(timezone.utc) - timedelta(minutes=20)
        t3 = datetime.now(timezone.utc) - timedelta(minutes=10)
        t4 = datetime.now(timezone.utc)

        # Removed 'project' from common_audit_fields to avoid duplication
        common_audit_fields_no_project = {"id": None, "prompt_text": "p", "response_text": "r", "remote_completion_id": "rc"}

        csv_backend.log_audit_event(AuditLogEntry(timestamp=t1, app_name="AppA", user_name="User1", log_type="info", model="m", project="P1", **common_audit_fields_no_project))
        csv_backend.log_audit_event(AuditLogEntry(timestamp=t2, app_name="AppB", user_name="User1", log_type="warning", model="m", project="P2", **common_audit_fields_no_project))
        csv_backend.log_audit_event(AuditLogEntry(timestamp=t3, app_name="AppA", user_name="User2", log_type="error", model="m", project="P1", **common_audit_fields_no_project))
        csv_backend.log_audit_event(AuditLogEntry(timestamp=t4, app_name="AppC", user_name="User1", log_type="info", model="ModelZ", project="P1", **common_audit_fields_no_project))

        logs_in_last_15_mins = csv_backend.get_audit_log_entries(limit=10, start_date=datetime.now(timezone.utc) - timedelta(minutes=15))
        assert len(logs_in_last_15_mins) == 2
        assert logs_in_last_15_mins[0].timestamp.replace(microsecond=0) == t4.replace(microsecond=0)
        assert logs_in_last_15_mins[1].timestamp.replace(microsecond=0) == t3.replace(microsecond=0)

        error_logs = csv_backend.get_audit_log_entries(limit=10, log_type="error")
        assert len(error_logs) == 1
        assert error_logs[0].user_name == "User2"
        
        page1_limit2 = csv_backend.get_audit_log_entries(limit=2) 
        assert len(page1_limit2) == 2
        assert page1_limit2[0].id == 4 
        assert page1_limit2[1].id == 3 

class TestPeriodStats:
    def test_get_period_stats_aggregation(self, csv_backend):
        t = datetime.now(timezone.utc)
        csv_backend.insert_usage(AccountingEntry(model="m1", total_tokens=30, timestamp=t - timedelta(hours=3)))
        csv_backend.insert_usage(AccountingEntry(model="m2", total_tokens=40, timestamp=t - timedelta(hours=2), username="u1", project="p1"))
        csv_backend.insert_usage(AccountingEntry(model="m1", total_tokens=50, timestamp=t - timedelta(hours=1), username="u2"))
        csv_backend.insert_usage(AccountingEntry(model="m3", total_tokens=200, timestamp=t + timedelta(hours=1)))

        start_time = t - timedelta(hours=2, minutes=30)
        end_time = t 
        stats = csv_backend.get_period_stats(start=start_time, end=end_time)
        assert stats.sum_total_tokens == 40 + 50

    def test_get_period_stats_empty_or_no_match(self, csv_backend):
        start_time = datetime.now(timezone.utc) - timedelta(days=1)
        end_time = datetime.now(timezone.utc)
        stats_empty = csv_backend.get_period_stats(start=start_time, end=end_time)
        assert stats_empty.sum_total_tokens == 0

class TestFileHandlingAndEdgeCases:
    def test_missing_files_recreated_on_operation(self, csv_backend, temp_data_dir):
        os.remove(csv_backend.accounting_file_path)
        csv_backend.insert_usage(AccountingEntry(model="m1", total_tokens=1, timestamp=datetime.now(timezone.utc)))
        assert os.path.exists(csv_backend.accounting_file_path)

    def test_type_conversions_datetime(self, csv_backend):
        now_utc_no_ms = datetime.now(timezone.utc).replace(microsecond=0)
        csv_backend.insert_usage(AccountingEntry(model="dt_test", total_tokens=1, timestamp=now_utc_no_ms))
        entry = csv_backend.tail(n=1, model="dt_test")[0]
        assert entry.timestamp == now_utc_no_ms

        csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.GLOBAL, limit_type="req", max_value=1, created_at=now_utc_no_ms, interval_unit="day", interval_value=1))
        ret_limit = csv_backend.get_usage_limits(scope=UsageLimitScope.GLOBAL)[0]
        assert ret_limit.created_at == now_utc_no_ms
        
        common_audit_fields = {"id":None, "prompt_text": "p", "response_text": "r", "remote_completion_id": "rc", "project": "proj"}
        csv_backend.log_audit_event(AuditLogEntry(log_type="info", timestamp=now_utc_no_ms, model="m", app_name="a", user_name="u", **common_audit_fields))
        all_audit_logs = sorted(csv_backend.get_audit_log_entries(limit=100), key=lambda x: x.timestamp if x.timestamp else datetime.min)
        audit = all_audit_logs[-1] if all_audit_logs else None
        assert audit is not None
        assert audit.timestamp == now_utc_no_ms
        
    def test_ids_auto_increment_from_empty_or_existing(self, csv_backend, temp_data_dir):
        assert csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type="t", max_value=1, interval_unit="day", interval_value=1)).id == 1
        assert csv_backend.insert_usage_limit(UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type="t", max_value=2, interval_unit="day", interval_value=1)).id == 2
        csv_backend.purge()
        
        common_audit_fields = {"id":None, "prompt_text": "p", "response_text": "r", "remote_completion_id": "rc", "project": "proj"}
        csv_backend.log_audit_event(AuditLogEntry(log_type="info", timestamp=datetime.now(timezone.utc), model="m", app_name="a", user_name="u", **common_audit_fields))
        csv_backend.log_audit_event(AuditLogEntry(log_type="info", timestamp=datetime.now(timezone.utc), model="m", app_name="a", user_name="u", **common_audit_fields))
        logs = sorted(csv_backend.get_audit_log_entries(limit=2), key=lambda x: x.timestamp if x.timestamp else datetime.min) 
        assert logs[0].id == 1
        assert logs[1].id == 2
        csv_backend.purge()

        csv_backend.insert_usage(AccountingEntry(id=None, model="m", total_tokens=1, timestamp=datetime.now(timezone.utc)))
        csv_backend.insert_usage(AccountingEntry(id=None, model="m", total_tokens=2, timestamp=datetime.now(timezone.utc)))
        acc_entries = csv_backend.tail(n=2)
        ids = sorted([e.id for e in acc_entries if e.id is not None]) 
        assert ids == [1, 2]


    def test_handling_io_error_on_init(self, tmp_path):
        unwriteable_dir = tmp_path / "unwriteable"
        unwriteable_dir.mkdir()
        os.chmod(str(unwriteable_dir), 0o444)
        if os.access(str(unwriteable_dir), os.W_OK):
            pytest.skip("Could not make directory read-only for testing IOError")
        with pytest.raises(IOError, match=f"Data directory '{str(unwriteable_dir)}' is not a writable directory."):
            CSVBackend(csv_data_dir=str(unwriteable_dir))
        os.chmod(str(unwriteable_dir), 0o777)
