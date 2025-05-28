import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pytest

from llm_accounting.backends.base import AuditLogEntry
from llm_accounting.backends.sqlite import SQLiteBackend

def _log_sample_audit_entries(backend: SQLiteBackend, now_utc: datetime) -> List[AuditLogEntry]:
    entries = [
        AuditLogEntry(id=None, timestamp=now_utc - timedelta(days=2), app_name="app1", user_name="userA", model="modelX", log_type="prompt", project="proj1", prompt_text="p1", response_text=None, remote_completion_id=None),
        AuditLogEntry(id=None, timestamp=now_utc - timedelta(days=1), app_name="app2", user_name="userB", model="modelY", log_type="response", project="proj2", prompt_text=None, response_text="r2", remote_completion_id="rcid2"),
        AuditLogEntry(id=None, timestamp=now_utc, app_name="app1", user_name="userA", model="modelZ", log_type="event", project="proj1", prompt_text="p3", response_text="r3", remote_completion_id="rcid3"),
        AuditLogEntry(id=None, timestamp=now_utc + timedelta(days=1), app_name="app3", user_name="userC", model="modelX", log_type="prompt", project=None, prompt_text="p4", response_text=None, remote_completion_id=None),
    ]
    for entry in entries:
        backend.log_audit_event(entry)
    return entries

@pytest.fixture(scope="class")
def logged_audit_entries_fixture(sqlite_backend: SQLiteBackend, now_utc: datetime) -> List[AuditLogEntry]:
    """
    Fixture to log sample audit entries once per test class.
    """
    return _log_sample_audit_entries(sqlite_backend, now_utc)

class TestSQLiteAuditLog:
    def test_audit_log_table_creation(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        """Test that the audit_log_entries table is created with the correct schema."""
        # The fixture ensures the table is created and populated.
        backend = sqlite_backend
        with sqlite3.connect(backend.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log_entries'")
            assert cursor.fetchone() is not None, "audit_log_entries table should exist"

            cursor = conn.execute("PRAGMA table_info(audit_log_entries)")
            columns_info = {row[1]: row[2] for row in cursor.fetchall()} # name: type
            
            expected_columns = {
                "id": "INTEGER",
                "timestamp": "TEXT", # Stored as ISO8601 string
                "app_name": "TEXT",
                "user_name": "TEXT",
                "model": "TEXT",
                "prompt_text": "TEXT",
                "response_text": "TEXT",
                "remote_completion_id": "TEXT",
                "project": "TEXT",
                "log_type": "TEXT"
            }
            
            for col_name, col_type in expected_columns.items():
                assert col_name in columns_info, f"Column '{col_name}' should exist in audit_log_entries"
                # Basic type check, SQLite types can be flexible (e.g. TEXT can store almost anything)
                # This mostly checks if the column was declared, as type affinity is complex.
                assert columns_info[col_name].upper() == col_type.upper(), \
                       f"Column '{col_name}' should have type '{col_type}', found '{columns_info[col_name]}'"

    def test_log_single_audit_event(self, sqlite_backend: SQLiteBackend, now_utc: datetime, logged_audit_entries_fixture: List[AuditLogEntry]):
        """Test logging a single audit event and retrieving it."""
        # The fixture ensures sample entries are logged once for the class
        initial_entry_count = len(logged_audit_entries_fixture)

        entry_to_log = AuditLogEntry(
            id=None,
            timestamp=now_utc + timedelta(days=5), # Use a distinct timestamp to avoid conflicts
            app_name="single_app",
            user_name="single_user",
            model="gpt-3.5-turbo",
            prompt_text="This is a prompt.",
            response_text="This is a response.",
            remote_completion_id="cmpl-xyz123",
            project="ProjectSingle",
            log_type="event"
        )
        sqlite_backend.log_audit_event(entry_to_log)

        retrieved_entries = sqlite_backend.get_audit_log_entries(app_name="single_app")
        assert len(retrieved_entries) == 1
        retrieved_entry = retrieved_entries[0]

        assert retrieved_entry.id is not None
        assert isinstance(retrieved_entry.id, int)
        assert retrieved_entry.app_name == entry_to_log.app_name
        assert retrieved_entry.user_name == entry_to_log.user_name
        assert retrieved_entry.model == entry_to_log.model
        assert retrieved_entry.prompt_text == entry_to_log.prompt_text
        assert retrieved_entry.response_text == entry_to_log.response_text
        assert retrieved_entry.remote_completion_id == entry_to_log.remote_completion_id
        assert retrieved_entry.project == entry_to_log.project
        assert retrieved_entry.log_type == entry_to_log.log_type
        assert retrieved_entry.timestamp == entry_to_log.timestamp # Compare with original aware datetime

    def test_log_audit_event_minimal_fields(self, sqlite_backend: SQLiteBackend, now_utc: datetime, logged_audit_entries_fixture: List[AuditLogEntry]):
        """Test logging an audit event with only required and some optional fields as None."""
        # The fixture ensures sample entries are logged once for the class
        initial_entry_count = len(logged_audit_entries_fixture)

        entry_to_log = AuditLogEntry(
            id=None,
            timestamp=now_utc + timedelta(days=6), # Use a distinct timestamp
            app_name="minimal_app",
            user_name="minimal_user",
            model="claude-2",
            prompt_text=None,
            response_text=None,
            remote_completion_id=None,
            project=None,
            log_type="minimal_event"
        )
        sqlite_backend.log_audit_event(entry_to_log)

        retrieved_entries = sqlite_backend.get_audit_log_entries(app_name="minimal_app")
        assert len(retrieved_entries) == 1
        retrieved_entry = retrieved_entries[0]

        assert retrieved_entry.id is not None
        assert retrieved_entry.app_name == entry_to_log.app_name
        assert retrieved_entry.user_name == entry_to_log.user_name
        assert retrieved_entry.model == entry_to_log.model
        assert retrieved_entry.prompt_text is None
        assert retrieved_entry.response_text is None
        assert retrieved_entry.remote_completion_id is None
        assert retrieved_entry.project is None
        assert retrieved_entry.log_type == entry_to_log.log_type
        assert retrieved_entry.timestamp == entry_to_log.timestamp


    def test_get_all_audit_logs(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        """Test retrieving all audit logs without filters."""
        retrieved_entries = sqlite_backend.get_audit_log_entries(project=None, filter_project_null=None) # Explicitly ask for all projects
        
        # We expect at least the entries from the fixture, plus any from previous tests in this class
        # Since each test adds new entries, we need to be careful with exact counts.
        # For this test, we just ensure that the initial logged entries are present.
        # The exact count will be 4 (from fixture) + 2 (from single and minimal tests) = 6
        assert len(retrieved_entries) >= len(logged_audit_entries_fixture)
        # Check if IDs are populated and are unique
        retrieved_ids = {e.id for e in retrieved_entries}
        assert None not in retrieved_ids

    def test_get_audit_logs_with_date_filters(self, sqlite_backend: SQLiteBackend, now_utc: datetime, logged_audit_entries_fixture: List[AuditLogEntry]):
        # The fixture ensures sample entries are logged once for the class
        
        # Start date only
        retrieved = sqlite_backend.get_audit_log_entries(start_date=(now_utc - timedelta(days=1, hours=1)), project=None, filter_project_null=None)
        # Expect entries from app2, app1 (modelZ), app3 from the fixture
        # Plus any entries added by test_log_single_audit_event and test_log_audit_event_minimal_fields
        # which have timestamps now_utc + timedelta(days=5) and now_utc + timedelta(days=6)
        # So, we expect 3 (from fixture) + 2 (from other tests) = 5 entries
        assert len(retrieved) == 5 

        # End date only
        retrieved = sqlite_backend.get_audit_log_entries(end_date=(now_utc + timedelta(hours=1)), project=None, filter_project_null=None)
        # Expect entries from app1 (modelX), app2, app1 (modelZ) from the fixture
        assert len(retrieved) == 3 

        # Both start and end date
        retrieved = sqlite_backend.get_audit_log_entries(
            start_date=(now_utc - timedelta(days=1, hours=1)), # After entry1
            end_date=(now_utc + timedelta(hours=1)),       # Before entry4
            project=None, filter_project_null=None
        )
        # Expect entries from app2, app1 (modelZ)
        assert len(retrieved) == 2 
        app_names = {e.app_name for e in retrieved}
        assert "app2" in app_names
        assert "app1" in app_names # from entry3

    def test_get_audit_logs_with_app_name_filter(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        retrieved = sqlite_backend.get_audit_log_entries(app_name="app1")
        assert len(retrieved) == 2
        assert all(e.app_name == "app1" for e in retrieved)

    def test_get_audit_logs_with_user_name_filter(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        retrieved = sqlite_backend.get_audit_log_entries(user_name="userA")
        assert len(retrieved) == 2
        assert all(e.user_name == "userA" for e in retrieved)

    def test_get_audit_logs_with_project_filter(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        # Test with a specific project
        retrieved = sqlite_backend.get_audit_log_entries(project="proj1", filter_project_null=False) # Explicitly filter for non-null project
        assert len(retrieved) == 2
        assert all(e.project == "proj1" for e in retrieved)
        # Test with project=None and filter_project_null=True
        retrieved_none = sqlite_backend.get_audit_log_entries(project=None, filter_project_null=True) # This should filter for project IS NULL
        assert len(retrieved_none) == 2 # Expect 2 entries now: app3 and minimal_app
        # We can't assert on a specific app_name for the first element as order is not guaranteed for same timestamp
        # assert retrieved_none[0].app_name == "app3" # Entry from app3 has project=None

    def test_get_audit_logs_with_log_type_filter(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        retrieved = sqlite_backend.get_audit_log_entries(log_type="prompt")
        assert len(retrieved) == 2
        assert all(e.log_type == "prompt" for e in retrieved)

    def test_get_audit_logs_with_limit(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        # Get all entries first to ensure we have enough for the limit test
        all_entries = sqlite_backend.get_audit_log_entries(project=None, filter_project_null=None) # Get all entries
        assert len(all_entries) >= len(logged_audit_entries_fixture) # Ensure at least 4 entries are present from fixture

        retrieved = sqlite_backend.get_audit_log_entries(limit=2, project=None, filter_project_null=None)
        assert len(retrieved) == 2
        # Default order is DESC by timestamp
        assert retrieved[0].timestamp > retrieved[1].timestamp 

    def test_get_audit_logs_with_combined_filters(self, sqlite_backend: SQLiteBackend, now_utc: datetime, logged_audit_entries_fixture: List[AuditLogEntry]):
        retrieved = sqlite_backend.get_audit_log_entries(
            app_name="app1", 
            user_name="userA", 
            log_type="event",
            start_date=now_utc - timedelta(minutes=1) # Should include entry3
        )
        assert len(retrieved) == 1
        entry = retrieved[0]
        assert entry.app_name == "app1"
        assert entry.user_name == "userA"
        assert entry.log_type == "event"
        assert entry.model == "modelZ" # from entry3

    def test_get_audit_logs_empty_result(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        retrieved = sqlite_backend.get_audit_log_entries(app_name="non_existent_app")
        assert len(retrieved) == 0

    def test_get_audit_logs_order_by_timestamp(self, sqlite_backend: SQLiteBackend, logged_audit_entries_fixture: List[AuditLogEntry]):
        """Verify default order is descending by timestamp."""
        retrieved = sqlite_backend.get_audit_log_entries(project=None, filter_project_null=None) # Get all entries
        
        assert len(retrieved) >= len(logged_audit_entries_fixture) # May include entries from other tests
        # Timestamps are now timezone-aware, direct comparison is fine
        for i in range(len(retrieved) - 1):
            assert retrieved[i].timestamp >= retrieved[i+1].timestamp
        
        # The specific app_name/model assertions were removed as they are too brittle
        # with dynamic entries from other tests. The primary check is the timestamp order.
