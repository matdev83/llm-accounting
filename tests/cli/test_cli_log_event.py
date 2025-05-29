import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from llm_accounting.cli.main import main as cli_main
from llm_accounting import LLMAccounting, SQLiteBackend
from llm_accounting.audit_log import AuditLogger

@pytest.fixture
def temp_db_path_with_audit_log_table(tmp_path):
    """Create a temporary SQLite DB and initialize the audit_log table."""
    db_path_str = str(tmp_path / "test_audit.sqlite")
    sqlite_backend = SQLiteBackend(db_path=db_path_str)
    accounting = LLMAccounting(backend=sqlite_backend)
    with accounting:
        pass
    return db_path_str

def run_cli_command(db_file_path, command_args):
    """Helper function to run CLI commands."""
    base_args = ["llm-accounting", "--db-file", db_file_path]
    full_args = base_args + command_args
    with patch('sys.argv', full_args):
        cli_main()


def test_log_event_basic(capsys, temp_db_path_with_audit_log_table):
    """Test basic invocation of the log-event command."""
    db_file = temp_db_path_with_audit_log_table
    app_name = "test_app_basic"
    user_name = "test_user_basic"

    command_args = [
        "log-event",
        "--app-name", app_name,
        "--user-name", user_name,
        "--model", "gpt-basic",
        "--log-type", "completion",
        "--prompt-text", "Hello",
        "--response-text", "World",
        "--project", "pytest_project_basic"
    ]
    
    run_cli_command(db_file, command_args)
    
    captured = capsys.readouterr() 
    assert f"Successfully logged event for app '{app_name}' and user '{user_name}'." in captured.out

    # Verify data was logged (optional for basic, but good for sanity)
    sqlite_backend = SQLiteBackend(db_path=db_file)
    accounting = LLMAccounting(backend=sqlite_backend)
    with accounting:
        audit_logger: AuditLogger = accounting.audit_logger
        entries = audit_logger.get_entries(app_name=app_name, user_name=user_name, limit=1)
    assert len(entries) == 1

def test_log_event_persists_data(capsys, temp_db_path_with_audit_log_table):
    """Test that log-event command correctly persists data to the database."""
    db_file = temp_db_path_with_audit_log_table
    app_name = "test_app_persist"
    user_name = "test_user_persist"
    model = "gpt-persist"
    log_type = "feedback"
    project = "pytest_project_persist"
    prompt = "Question?"
    response = "Answer."
    remote_id = "comp-12345"

    command_args = [
        "log-event",
        "--app-name", app_name,
        "--user-name", user_name,
        "--model", model,
        "--log-type", log_type,
        "--prompt-text", prompt,
        "--response-text", response,
        "--remote-completion-id", remote_id,
        "--project", project
    ]

    run_cli_command(db_file, command_args)
    
    captured = capsys.readouterr()
    assert f"Successfully logged event for app '{app_name}' and user '{user_name}'." in captured.out

    sqlite_backend = SQLiteBackend(db_path=db_file)
    accounting = LLMAccounting(backend=sqlite_backend)
    with accounting:
        audit_logger: AuditLogger = accounting.audit_logger
        # Removed order_by="timestamp DESC"
        entries = audit_logger.get_entries(app_name=app_name, user_name=user_name, limit=1)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.app_name == app_name
    assert entry.user_name == user_name
    assert entry.model == model
    assert entry.log_type == log_type
    assert entry.prompt_text == prompt
    assert entry.response_text == response
    assert entry.remote_completion_id == remote_id
    assert entry.project == project
    assert isinstance(entry.timestamp, datetime)
    assert (datetime.now(timezone.utc) - entry.timestamp).total_seconds() < 10

def test_log_event_with_timestamp(capsys, temp_db_path_with_audit_log_table):
    """Test log-event command with a specific timestamp."""
    db_file = temp_db_path_with_audit_log_table
    app_name = "test_app_ts"
    user_name = "test_user_ts"
    timestamp_str_input = "2023-10-26 10:00:00"
    expected_timestamp = datetime(2023, 10, 26, 10, 0, 0, tzinfo=timezone.utc)

    command_args = [
        "log-event",
        "--app-name", app_name,
        "--user-name", user_name,
        "--model", "gpt-ts",
        "--log-type", "test_log",
        "--timestamp", timestamp_str_input
    ]
    
    run_cli_command(db_file, command_args)

    captured = capsys.readouterr()
    assert f"Successfully logged event for app '{app_name}' and user '{user_name}'." in captured.out

    sqlite_backend = SQLiteBackend(db_path=db_file)
    accounting = LLMAccounting(backend=sqlite_backend)
    with accounting:
        audit_logger: AuditLogger = accounting.audit_logger
        # Removed order_by="timestamp DESC"
        entries = audit_logger.get_entries(app_name=app_name, user_name=user_name, limit=1)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.timestamp == expected_timestamp

def test_log_event_with_iso_timestamp_and_tz(capsys, temp_db_path_with_audit_log_table):
    """Test log-event command with a specific ISO timestamp including timezone."""
    db_file = temp_db_path_with_audit_log_table
    app_name = "test_app_iso_ts"
    user_name = "test_user_iso_ts"
    timestamp_str_input = "2023-10-26T14:30:00+02:00"
    expected_timestamp = datetime.fromisoformat(timestamp_str_input).astimezone(timezone.utc)

    command_args = [
        "log-event",
        "--app-name", app_name,
        "--user-name", user_name,
        "--model", "gpt-iso-ts",
        "--log-type", "iso_test_log",
        "--timestamp", timestamp_str_input
    ]

    run_cli_command(db_file, command_args)

    captured = capsys.readouterr()
    assert f"Successfully logged event for app '{app_name}' and user '{user_name}'." in captured.out

    sqlite_backend = SQLiteBackend(db_path=db_file)
    accounting = LLMAccounting(backend=sqlite_backend)
    with accounting:
        audit_logger: AuditLogger = accounting.audit_logger
        # Removed order_by="timestamp DESC"
        entries = audit_logger.get_entries(app_name=app_name, user_name=user_name, limit=1)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.timestamp == expected_timestamp

def test_log_event_timestamp_parse_error(capsys, temp_db_path_with_audit_log_table):
    """Test log-event command with an invalid timestamp format."""
    db_file = temp_db_path_with_audit_log_table
    app_name = "test_app_ts_error"
    user_name = "test_user_ts_error"
    timestamp_str_input = "invalid-date-format"

    command_args = [
        "log-event",
        "--app-name", app_name,
        "--user-name", user_name,
        "--model", "gpt-ts-error",
        "--log-type", "error_log",
        "--timestamp", timestamp_str_input
    ]
    
    run_cli_command(db_file, command_args)

    captured = capsys.readouterr()
    assert f"Error: Could not parse provided timestamp '{timestamp_str_input}'." in captured.out
    assert f"Successfully logged event for app '{app_name}' and user '{user_name}'." not in captured.out

    sqlite_backend = SQLiteBackend(db_path=db_file)
    accounting = LLMAccounting(backend=sqlite_backend)
    with accounting:
        audit_logger: AuditLogger = accounting.audit_logger
        entries = audit_logger.get_entries(app_name=app_name, user_name=user_name)
    assert len(entries) == 0
