import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
import time # For time.sleep
import re # Added for re.escape
from typing import Generator
from llm_accounting import AuditLogger # Assuming it's exposed in __init__

# Expected columns in the audit_log_entries table
EXPECTED_COLUMNS = {
    "id", "timestamp", "app_name", "user_name", "model",
    "prompt_text", "response_text", "remote_completion_id", "log_type"
}

# --- Fixtures ---

@pytest.fixture
def memory_logger():
    """Provides an AuditLogger instance using an in-memory SQLite database."""
    logger = AuditLogger(db_path=":memory:")
    with logger as al: # Ensures connection is made and schema is initialized
        yield al
    # Connection is automatically closed by __exit__

@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Provides a path to a temporary database file."""
    db_file = tmp_path / "test_audit.sqlite"
    # Ensure the file does not exist from a previous run if not cleaned up properly
    if db_file.exists():
        db_file.unlink()
    return db_file

@pytest.fixture
def file_logger(temp_db_path: Path) -> Generator[AuditLogger, None, None]:
    """Provides an AuditLogger instance using a temporary file-based SQLite database."""
    logger = AuditLogger(db_path=str(temp_db_path))
    # No need to open/close here, tests will handle it or use context manager
    yield logger
    # Clean up the database file after the test
    if temp_db_path.exists():
        temp_db_path.unlink()


# --- Helper Functions ---

def get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """Retrieves the column names of a given table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}

def fetch_all_entries(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Fetches all rows from the audit_log_entries table."""
    conn.row_factory = sqlite3.Row # Access columns by name
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log_entries")
    return cursor.fetchall()

def is_iso8601(timestamp_str: str) -> bool:
    """Checks if a string is a valid ISO 8601 timestamp."""
    try:
        datetime.fromisoformat(timestamp_str)
        return True
    except ValueError:
        return False

# --- Test Cases ---

def test_db_and_table_creation_memory(memory_logger: AuditLogger):
    """Tests database and table creation with an in-memory database."""
    assert memory_logger.conn is not None, "Connection should be active within context manager"
    columns = get_table_columns(memory_logger.conn, "audit_log_entries")
    assert columns == EXPECTED_COLUMNS, f"Table columns do not match expected. Got: {columns}"

def test_db_and_table_creation_file(file_logger: AuditLogger):
    """Tests database and table creation with a file-based database."""
    assert file_logger.conn is None, "Connection should not be active initially"
    with file_logger as al:
        assert al.conn is not None, "Connection should be active within context manager"
        assert Path(al.db_path).exists(), "Database file should be created"
        columns = get_table_columns(al.conn, "audit_log_entries")
        assert columns == EXPECTED_COLUMNS
    assert file_logger.conn is None, "Connection should be closed after exiting context"

def test_log_prompt(memory_logger: AuditLogger):
    """Tests the log_prompt method."""
    al = memory_logger
    app_name = "test_app_prompt"
    user_name = "test_user_prompt"
    model = "gpt-test-prompt"
    prompt_text = "This is a test prompt."
    
    # Test without providing timestamp
    before_log_utc = datetime.now(timezone.utc)
    al.log_prompt(app_name, user_name, model, prompt_text)
    after_log_utc = datetime.now(timezone.utc)

    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    entry = entries[0]

    assert entry["app_name"] == app_name
    assert entry["user_name"] == user_name
    assert entry["model"] == model
    assert entry["prompt_text"] == prompt_text
    assert entry["log_type"] == "prompt"
    assert entry["response_text"] is None
    assert entry["remote_completion_id"] is None
    
    assert is_iso8601(entry["timestamp"]), "Timestamp is not valid ISO 8601"
    logged_time = datetime.fromisoformat(entry["timestamp"]).replace(tzinfo=timezone.utc)
    # Allow a small delta for execution time
    assert before_log_utc - timedelta(seconds=1) <= logged_time <= after_log_utc + timedelta(seconds=1)

    # Test with providing timestamp
    custom_ts = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    al.log_prompt(app_name, user_name, model, "Another prompt", timestamp=custom_ts)
    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    entry_with_custom_ts = entries[1]
    assert entry_with_custom_ts["timestamp"] == custom_ts.isoformat()


def test_log_response(memory_logger: AuditLogger):
    """Tests the log_response method."""
    al = memory_logger
    app_name = "test_app_response"
    user_name = "test_user_response"
    model = "gpt-test-response"
    response_text = "This is a test response."
    completion_id = "cmpl-test123"

    # Log with remote_completion_id
    before_log_utc = datetime.now(timezone.utc)
    al.log_response(app_name, user_name, model, response_text, remote_completion_id=completion_id)
    after_log_utc = datetime.now(timezone.utc)

    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    entry1 = entries[0]

    assert entry1["app_name"] == app_name
    assert entry1["user_name"] == user_name
    assert entry1["model"] == model
    assert entry1["response_text"] == response_text
    assert entry1["remote_completion_id"] == completion_id
    assert entry1["log_type"] == "response"
    assert entry1["prompt_text"] is None
    
    assert is_iso8601(entry1["timestamp"]), "Timestamp is not valid ISO 8601 (entry1)"
    logged_time1 = datetime.fromisoformat(entry1["timestamp"]).replace(tzinfo=timezone.utc)
    assert before_log_utc - timedelta(seconds=1) <= logged_time1 <= after_log_utc + timedelta(seconds=1)

    # Log without remote_completion_id and with custom timestamp
    custom_ts = datetime(2023, 5, 5, 10, 30, 0, tzinfo=timezone.utc)
    al.log_response(app_name, user_name, model, "Another response.", timestamp=custom_ts)
    
    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 2
    entry2 = entries[1]

    assert entry2["remote_completion_id"] is None
    assert entry2["prompt_text"] is None
    assert entry2["log_type"] == "response"
    assert entry2["timestamp"] == custom_ts.isoformat()


def test_context_manager_usage(temp_db_path: Path):
    """Tests AuditLogger as a context manager."""
    logger = AuditLogger(db_path=str(temp_db_path))
    assert logger.conn is None, "Connection should be None before entering context"
    
    with logger as al:
        assert al.conn is not None, "Connection should be established within context"
        assert isinstance(al.conn, sqlite3.Connection), "conn should be a sqlite3.Connection object"
        # Perform a simple operation
        al.log_prompt("ctx_app", "ctx_user", "ctx_model", "ctx_prompt")
    
    assert logger.conn is None, "Connection should be closed after exiting context"
    
    # Verify data was written and connection is closed by trying to read
    conn = sqlite3.connect(str(temp_db_path))
    entries = fetch_all_entries(conn)
    conn.close()
    assert len(entries) == 1
    assert entries[0]["app_name"] == "ctx_app"


def test_nullable_fields(memory_logger: AuditLogger):
    """Tests that fields intended to be nullable are indeed nullable."""
    al = memory_logger

    # Test log_prompt (response_text and remote_completion_id should be NULL)
    al.log_prompt("null_app", "null_user", "null_model", "prompt for null test")
    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    prompt_entry = entries[0]
    assert prompt_entry["response_text"] is None
    assert prompt_entry["remote_completion_id"] is None

    # Test log_response (prompt_text should be NULL, remote_completion_id can be NULL)
    al.log_response("null_app", "null_user", "null_model", "response for null test", remote_completion_id=None)
    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 2
    response_entry = entries[1]
    assert response_entry["prompt_text"] is None
    assert response_entry["remote_completion_id"] is None # Explicitly set to None

    al.log_response("null_app", "null_user", "null_model", "response with id", remote_completion_id="id_test")
    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 3
    response_entry_with_id = entries[2]
    assert response_entry_with_id["prompt_text"] is None
    assert response_entry_with_id["remote_completion_id"] == "id_test"


def test_custom_db_path(temp_db_path: Path):
    """Tests AuditLogger with a custom database path."""
    custom_path_logger = AuditLogger(db_path=str(temp_db_path))
    assert custom_path_logger.db_path == str(temp_db_path)
    
    with custom_path_logger as al:
        assert Path(al.db_path).exists(), "Database file should be created at custom path"
        al.log_prompt("custom_path_app", "custom_user", "custom_model", "custom_prompt")

    # Verify data is in the custom path DB
    conn = sqlite3.connect(str(temp_db_path))
    entries = fetch_all_entries(conn)
    conn.close()
    assert len(entries) == 1
    assert entries[0]["app_name"] == "custom_path_app"
    
    # Ensure the fixture cleans up this file

def test_log_event_method(memory_logger: AuditLogger):
    """Tests the generic log_event method for completeness."""
    al = memory_logger
    app_name = "generic_app"
    user_name = "generic_user"
    model = "generic_model"
    prompt = "generic_prompt"
    response = "generic_response"
    remote_id = "cmpl-generic"
    custom_ts = datetime(2023, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Log a prompt-like event
    al.log_event(
        app_name=app_name, user_name=user_name, model=model, log_type="prompt",
        prompt_text=prompt, timestamp=custom_ts
    )
    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    entry1 = entries[0]
    assert entry1["app_name"] == app_name
    assert entry1["user_name"] == user_name
    assert entry1["model"] == model
    assert entry1["log_type"] == "prompt"
    assert entry1["prompt_text"] == prompt
    assert entry1["response_text"] is None
    assert entry1["remote_completion_id"] is None
    assert entry1["timestamp"] == custom_ts.isoformat()

    # Log a response-like event
    al.log_event(
        app_name=app_name, user_name=user_name, model=model, log_type="response",
        response_text=response, remote_completion_id=remote_id
    )
    assert al.conn is not None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 2
    entry2 = entries[1]
    assert entry2["log_type"] == "response"
    assert entry2["response_text"] == response
    assert entry2["remote_completion_id"] == remote_id
    assert entry2["prompt_text"] is None
    assert is_iso8601(entry2["timestamp"]) # Default timestamp check

def test_connection_error_if_not_connected(file_logger: AuditLogger):
    """Tests that methods raise ConnectionError if used before connecting (outside context manager)."""
    # file_logger is not yet connected
    assert file_logger.conn is None
    with pytest.raises(ConnectionError, match="Database connection is not open."):
        file_logger.log_event("app", "user", "model", "prompt")
    
    with pytest.raises(ConnectionError, match=re.escape("Database connection is not open. Call connect() or use a context manager.")):
        file_logger.log_prompt("app", "user", "model", "prompt")

    with pytest.raises(ConnectionError, match=re.escape("Database connection is not open. Call connect() or use a context manager.")):
        file_logger.log_response("app", "user", "model", "response")

    # Test that connect works
    file_logger.connect()
    assert file_logger.conn is not None
    file_logger.log_prompt("app", "user", "model", "prompt after connect") # Should not raise
    assert file_logger.conn is not None
    entries = fetch_all_entries(file_logger.conn)
    assert len(entries) == 1
    file_logger.close()
    assert file_logger.conn is None

def test_parent_directory_creation(tmp_path: Path):
    """Tests that AuditLogger creates parent directories for the db_path if they don't exist."""
    deep_db_path = tmp_path / "deep" / "nested" / "audit.sqlite"
    assert not deep_db_path.parent.exists()

    logger = AuditLogger(db_path=str(deep_db_path))
    with logger as al:
        assert deep_db_path.parent.exists()
        assert deep_db_path.exists()
        al.log_prompt("deep_app", "deep_user", "deep_model", "deep_prompt")

    assert deep_db_path.exists() # Should persist after closing

    # Clean up
    deep_db_path.unlink()
    deep_db_path.parent.rmdir()
    deep_db_path.parent.parent.rmdir()

# # A simple test to ensure the example from audit_log.py still runs
# def test_main_example_runs(tmp_path, capsys):
#     """
#     This test is a bit more of an integration test for the example block.
#     It checks if the example code runs without error and produces some expected output.
#     This will create 'data/audit_log_main.sqlite' and 'data/custom_audit_main.sqlite'
#     in the *current working directory* where pytest is run, which is not ideal.
#     We will redirect them to tmp_path.
#     """
#     original_default_db_file = "data/audit_log_main.sqlite"
#     original_custom_db_file = "data/custom_audit_main.sqlite"

#     # Create dummy original files in tmp_path to avoid FileNotFoundError if they don't exist
#     # The script attempts to delete these.
#     # (Path(original_default_db_file).parent).mkdir(parents=True, exist_ok=True)
#     # (Path(original_custom_db_file).parent).mkdir(parents=True, exist_ok=True)
#     # Path(original_default_db_file).touch()
#     # Path(original_custom_db_file).touch()


#     # Monkeypatch pathlib.Path.unlink and rmdir to track calls and avoid errors
#     # if files/dirs don't exist as expected by the original script's cleanup.
#     # This is getting complex, perhaps the __main__ block should be more testable.
    
#     # For now, let's just run it and check for no exceptions.
#     # The __main__ block in audit_log.py has hardcoded paths "data/..."
#     # which is not great for testing. We'll let it run and create those.
#     # The fixture 'file_logger' and 'temp_db_path' handle their own temporary files.

#     try:
#         # This will run the __main__ block in audit_log.py
#         import src.llm_accounting.audit_log
#         # To re-run the main block if it was already imported and run:
#         # import importlib
#         # importlib.reload(src.llm_accounting.audit_log)

#         # Check if the files were created by the __main__ block
#         # These are hardcoded in the __main__ block of audit_log.py
#         main_default_db = Path("data/audit_log_main.sqlite")
#         main_custom_db = Path("data/custom_audit_main.sqlite")

#         assert main_default_db.exists()
#         assert main_custom_db.exists()

#         # Minimal check of output (optional, depends on script's verbosity)
#         captured = capsys.readouterr()
#         assert "Logged a prompt and a response via log_event" in captured.out
#         assert "Logged to custom DB via new methods" in captured.out

#     finally:
#         # Clean up files created by the __main__ block
#         default_db_in_main = Path("data/audit_log_main.sqlite")
#         custom_db_in_main = Path("data/custom_audit_main.sqlite")
#         data_dir = Path("data")

#         default_db_in_main.unlink(missing_ok=True)
#         custom_db_in_main.unlink(missing_ok=True)
        
#         # Try to remove 'data' directory if it's empty
#         try:
#             if data_dir.exists() and not any(data_dir.iterdir()):
#                 data_dir.rmdir()
#         except OSError:
#             print(f"Warning: Could not remove {data_dir} during test cleanup.")

# # Note: The test_main_example_runs is a bit fragile because it depends on the
# # exact output and file creation logic of the __main__ block in audit_log.py.
# # It's often better to refactor __main__ blocks to be more easily callable
# # and configurable for testing.
