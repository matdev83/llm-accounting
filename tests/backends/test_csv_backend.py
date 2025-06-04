import pytest
import os
import csv
import shutil
from pathlib import Path 
from datetime import datetime, timedelta, timezone
from typing import List # Import List

from llm_accounting.backends.csv_backend import CSVBackend
from llm_accounting.backends.base import AuditLogEntry as BaseAuditLogEntry, UsageEntry as BaseUsageEntry, UsageStats as BaseUsageStats
from llm_accounting.models.limits import UsageLimitDTO as BaseUsageLimitDTO, LimitScope as BaseLimitScope, LimitType as BaseLimitType

# Aliases for the test file
AccountingEntry = BaseUsageEntry
PeriodStats = BaseUsageStats
UsageLimitDTO = BaseUsageLimitDTO
UsageLimitScope = BaseLimitScope
AuditLogEntry = BaseAuditLogEntry
LimitType = BaseLimitType


# Helper function to get header of a csv file
def get_csv_header(file_path: str) -> List[str]:
    file = Path(file_path)
    if not file.exists() or file.stat().st_size == 0:
        return []
    with open(file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            return next(reader)
        except StopIteration:
            return []

# Helper function to count data rows in a csv file (excluding header)
def count_csv_data_rows(file_path: str) -> int:
    file = Path(file_path)
    if not file.exists() or file.stat().st_size == 0:
        return 0
    with open(file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None) 
        if not header:
            return 0
        return sum(1 for row in reader)


@pytest.fixture
def temp_data_dir_str(tmp_path: Path) -> str: 
    data_dir = tmp_path / "csv_data_fixture"
    data_dir.mkdir()
    return str(data_dir)

@pytest.fixture
def csv_backend_fixture(temp_data_dir_str: str) -> CSVBackend:
    backend = CSVBackend(data_dir=temp_data_dir_str) 
    return backend

class TestCSVBackendInitialization:
    def test_initialization_default_dir(self, tmp_path: Path):
        original_default_dir = CSVBackend.DEFAULT_DATA_DIR
        test_default_dir = tmp_path / "test_default_data_dir"
        CSVBackend.DEFAULT_DATA_DIR = str(test_default_dir)
        
        try:
            backend = CSVBackend() 
            
            data_dir_path = Path(backend.data_dir)
            assert data_dir_path.exists()
            assert data_dir_path.is_dir()
            assert data_dir_path == test_default_dir

            acc_file = Path(backend.accounting_file)
            audit_file = Path(backend.audit_file)
            limits_file = Path(backend.limits_file)

            assert acc_file.exists() and acc_file.is_file()
            assert audit_file.exists() and audit_file.is_file()
            assert limits_file.exists() and limits_file.is_file()

            assert get_csv_header(str(acc_file)) == CSVBackend.ACCOUNTING_FIELDNAMES
            assert get_csv_header(str(audit_file)) == CSVBackend.AUDIT_FIELDNAMES
            assert get_csv_header(str(limits_file)) == CSVBackend.LIMITS_FIELDNAMES
        finally:
            CSVBackend.DEFAULT_DATA_DIR = original_default_dir 
            if test_default_dir.exists():
                 shutil.rmtree(test_default_dir)


    def test_initialization_custom_dir(self, tmp_path: Path):
        custom_dir = tmp_path / "custom_csv_data"

        backend = CSVBackend(data_dir=str(custom_dir))
        
        data_dir_path = Path(backend.data_dir)
        assert data_dir_path.exists()
        assert data_dir_path.is_dir()
        assert data_dir_path == custom_dir
        
        acc_file = Path(backend.accounting_file)
        audit_file = Path(backend.audit_file)
        limits_file = Path(backend.limits_file)

        assert acc_file.exists() and acc_file.is_file()
        assert audit_file.exists() and audit_file.is_file()
        assert limits_file.exists() and limits_file.is_file()

        assert get_csv_header(str(acc_file)) == CSVBackend.ACCOUNTING_FIELDNAMES
        assert get_csv_header(str(audit_file)) == CSVBackend.AUDIT_FIELDNAMES
        assert get_csv_header(str(limits_file)) == CSVBackend.LIMITS_FIELDNAMES
        
        if custom_dir.exists(): 
            shutil.rmtree(custom_dir)


    def test_data_dir_creation(self, tmp_path: Path):
        non_existent_dir = tmp_path / "new_csv_data_to_be_created"
        assert not non_existent_dir.exists() 

        backend = CSVBackend(data_dir=str(non_existent_dir))
        
        data_dir_path = Path(backend.data_dir)
        assert data_dir_path.exists()
        assert data_dir_path.is_dir()
        assert data_dir_path == non_existent_dir
        
        assert Path(backend.accounting_file).exists() 
        
        if non_existent_dir.exists(): 
            shutil.rmtree(non_existent_dir)


    def test_initialization_existing_files(self, tmp_path: Path):
        existing_dir = tmp_path / "existing_csv_data"
        existing_dir.mkdir()

        acc_file_path = existing_dir / CSVBackend.ACCOUNTING_FILE_NAME
        audit_file_path = existing_dir / CSVBackend.AUDIT_FILE_NAME
        limits_file_path = existing_dir / CSVBackend.LIMITS_FILE_NAME

        with open(acc_file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSVBackend.ACCOUNTING_FIELDNAMES)
            writer.writerow(["dummy_id_acc"] + ["data"] * (len(CSVBackend.ACCOUNTING_FIELDNAMES) - 1))
        
        with open(audit_file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSVBackend.AUDIT_FIELDNAMES)
            writer.writerow(["dummy_id_audit"] + ["data"] * (len(CSVBackend.AUDIT_FIELDNAMES) - 1))

        with open(limits_file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSVBackend.LIMITS_FIELDNAMES)
            writer.writerow(["dummy_id_limit"] + ["data"] * (len(CSVBackend.LIMITS_FIELDNAMES) - 1))

        backend = CSVBackend(data_dir=str(existing_dir)) 

        assert acc_file_path.exists()
        assert audit_file_path.exists()
        assert limits_file_path.exists()

        assert get_csv_header(str(acc_file_path)) == CSVBackend.ACCOUNTING_FIELDNAMES
        
        assert count_csv_data_rows(str(acc_file_path)) == 1
        assert count_csv_data_rows(str(audit_file_path)) == 1
        assert count_csv_data_rows(str(limits_file_path)) == 1
        
        if existing_dir.exists(): 
             shutil.rmtree(existing_dir)

class TestCSVPurge:
    def test_purge_clears_data_keeps_headers(self, csv_backend_fixture: CSVBackend):
        backend = csv_backend_fixture
        
        accounting_file = Path(backend.accounting_file)
        audit_file = Path(backend.audit_file)
        limits_file = Path(backend.limits_file)

        with open(accounting_file, 'a', newline='') as f: csv.writer(f).writerow(['d1'] * len(CSVBackend.ACCOUNTING_FIELDNAMES))
        with open(audit_file, 'a', newline='') as f: csv.writer(f).writerow(['d1'] * len(CSVBackend.AUDIT_FIELDNAMES))
        with open(limits_file, 'a', newline='') as f: csv.writer(f).writerow(['d1'] * len(CSVBackend.LIMITS_FIELDNAMES))

        assert count_csv_data_rows(str(accounting_file)) == 1
        assert count_csv_data_rows(str(audit_file)) == 1
        assert count_csv_data_rows(str(limits_file)) == 1
        
        backend.purge()
        
        assert count_csv_data_rows(str(accounting_file)) == 0
        assert get_csv_header(str(accounting_file)) == CSVBackend.ACCOUNTING_FIELDNAMES
        
        assert count_csv_data_rows(str(audit_file)) == 0
        assert get_csv_header(str(audit_file)) == CSVBackend.AUDIT_FIELDNAMES

        assert count_csv_data_rows(str(limits_file)) == 0
        assert get_csv_header(str(limits_file)) == CSVBackend.LIMITS_FIELDNAMES

class TestAccountingEntries:
    def test_insert_and_tail_single_entry(self, csv_backend_fixture: CSVBackend):
        backend = csv_backend_fixture
        now = datetime.now(timezone.utc)
        entry = AccountingEntry(id=None, model="gpt-3.5-turbo", prompt_tokens=10, completion_tokens=20, total_tokens=30, cost=0.00015, timestamp=now, username="user1", project="projA")
        backend.insert_usage(entry)
        tailed_entries = backend.tail(n=1)
        assert len(tailed_entries) == 1
        retrieved = tailed_entries[0]
        # tail should return the same object that was inserted
        assert retrieved is entry
        assert retrieved.model == entry.model
        assert retrieved.username == entry.username
        assert retrieved.project == entry.project
        assert retrieved.id is not None

class TestUsageLimits:
    def test_insert_get_delete_usage_limit(self, csv_backend_fixture: CSVBackend):
        backend = csv_backend_fixture
        limit1 = UsageLimitDTO(id=None, scope=UsageLimitScope.USER, limit_type=LimitType.COST, model="gpt-4", username="test_user", max_value=10000, interval_unit="month", interval_value=1)
        backend.insert_usage_limit(limit1)
        retrieved = backend.get_usage_limits(username="test_user")
        assert len(retrieved) == 1
        stored_limit = retrieved[0]
        assert stored_limit.username == "test_user"
        assert stored_limit.max_value == 10000
        assert stored_limit.id is not None

        backend.delete_usage_limit(stored_limit.id)
        assert backend.get_usage_limits(username="test_user") == []

class TestAuditLog:
    def test_insert_get_audit_log_entry(self, csv_backend_fixture: CSVBackend):
        backend = csv_backend_fixture
        now = datetime.now(timezone.utc)
        entry1 = AuditLogEntry(
            id=None, timestamp=now, app_name="App1", user_name="UserA",
            model="ModelX", log_type="info", prompt_text="Hello",
            response_text="Hi there", remote_completion_id="remote1", project="ProjectAlpha"
        )
        backend.log_audit_event(entry1)
        logs = backend.get_audit_log_entries(app_name="App1")
        assert len(logs) == 1
        retrieved = logs[0]
        assert retrieved.app_name == "App1"
        assert retrieved.user_name == "UserA"
        assert retrieved.model == "ModelX"
        assert retrieved.id is not None

class TestPeriodStats:
    def test_get_period_stats_aggregation(self, csv_backend_fixture: CSVBackend):
        backend = csv_backend_fixture
        stats = backend.get_period_stats(start=datetime.now(), end=datetime.now())
        assert stats.sum_total_tokens == 0 

class TestFileHandlingAndEdgeCases:
    def test_missing_files_recreated_on_operation(self, csv_backend_fixture: CSVBackend, temp_data_dir_str: str):
        backend = csv_backend_fixture
        accounting_file = Path(backend.accounting_file)
        if accounting_file.exists():
            os.remove(accounting_file)
        
        backend_reinit = CSVBackend(data_dir=temp_data_dir_str)
        assert Path(backend_reinit.accounting_file).exists()

def test_handling_io_error_on_init_standalone(tmp_path: Path):
    unwriteable_dir = tmp_path / "unwriteable_for_csv"
    unwriteable_dir.mkdir()
    os.chmod(str(unwriteable_dir), 0o444) 
    
    if os.access(str(unwriteable_dir), os.W_OK):
        if "PYTEST_CURRENT_TEST" in os.environ:
             pytest.skip("Could not make directory read-only for testing IOError")
        else:
            print("Warning: Could not make directory read-only for testing IOError. Test might not be effective.")

    with pytest.raises(IOError): 
        CSVBackend(data_dir=str(unwriteable_dir))
    
    os.chmod(str(unwriteable_dir), 0o777) 
    if unwriteable_dir.exists():
        shutil.rmtree(unwriteable_dir)
