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
    "prompt_text", "response_text", "remote_completion_id", "log_type", "project"
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
    project_name = "ProjectAlpha"
    
    # Test without providing timestamp or project
    al.log_prompt(app_name, user_name, model, prompt_text)
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["project"] is None

    # Test with project
    al.log_prompt(app_name, user_name, model, prompt_text, project=project_name)
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 2
    entry_with_project = entries[1]
    assert entry_with_project["project"] == project_name
    
    # Original assertions for other fields
    assert entry_with_project["app_name"] == app_name
    assert entry_with_project["user_name"] == user_name
    assert entry_with_project["model"] == model
    assert entry_with_project["prompt_text"] == prompt_text
    assert entry_with_project["log_type"] == "prompt"


def test_log_response(memory_logger: AuditLogger):
    """Tests the log_response method."""
    al = memory_logger
    app_name = "test_app_response"
    user_name = "test_user_response"
    model = "gpt-test-response"
    response_text = "This is a test response."
    completion_id = "cmpl-test123"
    project_name = "ProjectBeta"

    # Log with remote_completion_id, without project
    al.log_response(app_name, user_name, model, response_text, remote_completion_id=completion_id)
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    entry1 = entries[0]
    assert entry1["project"] is None
    assert entry1["app_name"] == app_name # Basic check

    # Log with remote_completion_id and project
    al.log_response(app_name, user_name, model, response_text, remote_completion_id=completion_id, project=project_name)
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 2
    entry2 = entries[1]
    assert entry2["project"] == project_name
    assert entry2["app_name"] == app_name # Basic check


def test_log_event_method(memory_logger: AuditLogger):
    """Tests the generic log_event method for completeness, including project."""
    al = memory_logger
    app_name = "generic_app"
    user_name = "generic_user"
    model = "generic_model"
    prompt = "generic_prompt"
    response = "generic_response"
    remote_id = "cmpl-generic"
    project_name = "ProjectGamma"
    custom_ts = datetime(2023, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Log a prompt-like event without project
    al.log_event(
        app_name=app_name, user_name=user_name, model=model, log_type="prompt",
        prompt_text=prompt, timestamp=custom_ts
    )
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    entry1 = entries[0]
    assert entry1["project"] is None
    assert entry1["app_name"] == app_name # Basic check

    # Log a response-like event with project
    al.log_event(
        app_name=app_name, user_name=user_name, model=model, log_type="response",
        response_text=response, remote_completion_id=remote_id, project=project_name
    )
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 2
    entry2 = entries[1]
    assert entry2["project"] == project_name
    assert entry2["app_name"] == app_name # Basic check
    assert entry2["log_type"] == "response" # Check other field remains correct


def test_context_manager_usage(temp_db_path: Path):
    """Tests AuditLogger as a context manager."""
    logger = AuditLogger(db_path=str(temp_db_path))
    assert logger.conn is None, "Connection should be None before entering context"
    
    with logger as al:
        assert al.conn is not None, "Connection should be established within context"
        assert isinstance(al.conn, sqlite3.Connection), "conn should be a sqlite3.Connection object"
        # Perform a simple operation
        al.log_prompt("ctx_app", "ctx_user", "ctx_model", "ctx_prompt", project="CtxProject")
    
    assert logger.conn is None, "Connection should be closed after exiting context"
    
    # Verify data was written and connection is closed by trying to read
    conn = sqlite3.connect(str(temp_db_path))
    entries = fetch_all_entries(conn)
    conn.close()
    assert len(entries) == 1
    assert entries[0]["app_name"] == "ctx_app"
    assert entries[0]["project"] == "CtxProject"


def test_nullable_fields(memory_logger: AuditLogger):
    """Tests that fields intended to be nullable are indeed nullable, including project."""
    al = memory_logger

    # Test log_prompt (response_text and remote_completion_id should be NULL, project can be NULL)
    al.log_prompt("null_app", "null_user", "null_model", "prompt for null test") # project is None by default
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 1
    prompt_entry_no_proj = entries[0]
    assert prompt_entry_no_proj["response_text"] is None
    assert prompt_entry_no_proj["remote_completion_id"] is None
    assert prompt_entry_no_proj["project"] is None

    al.log_prompt("null_app", "null_user", "null_model", "prompt for null test with project", project="ProjectTest")
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 2
    prompt_entry_with_proj = entries[1]
    assert prompt_entry_with_proj["project"] == "ProjectTest"


    # Test log_response (prompt_text should be NULL, remote_completion_id can be NULL, project can be NULL)
    al.log_response("null_app", "null_user", "null_model", "response for null test", remote_completion_id=None) # project is None
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 3
    response_entry_no_proj = entries[2]
    assert response_entry_no_proj["prompt_text"] is None
    assert response_entry_no_proj["remote_completion_id"] is None
    assert response_entry_no_proj["project"] is None

    al.log_response("null_app", "null_user", "null_model", "response for null test with project", project="ProjectTest2")
    entries = fetch_all_entries(al.conn)
    assert len(entries) == 4
    response_entry_with_proj = entries[3]
    assert response_entry_with_proj["project"] == "ProjectTest2"


def test_custom_db_path(temp_db_path: Path):
    """Tests AuditLogger with a custom database path."""
    custom_path_logger = AuditLogger(db_path=str(temp_db_path))
    assert custom_path_logger.db_path == str(temp_db_path)
    
    with custom_path_logger as al:
        assert Path(al.db_path).exists(), "Database file should be created at custom path"
        al.log_prompt("custom_path_app", "custom_user", "custom_model", "custom_prompt", project="CustomPathProject")

    # Verify data is in the custom path DB
    conn = sqlite3.connect(str(temp_db_path))
    entries = fetch_all_entries(conn)
    conn.close()
    assert len(entries) == 1
    assert entries[0]["app_name"] == "custom_path_app"
    assert entries[0]["project"] == "CustomPathProject"
    

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
    # Logging with project to ensure new signature is also handled
    file_logger.log_prompt("app", "user", "model", "prompt after connect", project="ConnectProject") 
    assert file_logger.conn is not None
    entries = fetch_all_entries(file_logger.conn)
    assert len(entries) == 1
    assert entries[0]["project"] == "ConnectProject"
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
        al.log_prompt("deep_app", "deep_user", "deep_model", "deep_prompt", project="DeepProject")

    assert deep_db_path.exists() # Should persist after closing
    
    # Verify project was written
    conn = sqlite3.connect(str(deep_db_path))
    entries = fetch_all_entries(conn)
    conn.close()
    assert len(entries) == 1
    assert entries[0]["project"] == "DeepProject"


    # Clean up
    deep_db_path.unlink()
    deep_db_path.parent.rmdir()
    deep_db_path.parent.parent.rmdir()
