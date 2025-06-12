import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, call # Added Mock and call
from typing import List # Added List

from llm_accounting.audit_log import AuditLogger
from llm_accounting.backends.base import AuditBackend, AuditLogEntry

# EXPECTED_COLUMNS removed
# Old fixtures (memory_logger, temp_db_path, file_logger) removed
# Old helper functions (get_table_columns, fetch_all_entries, is_iso8601) removed

# --- New Fixtures ---

@pytest.fixture
def mock_backend() -> Mock:
    """Provides a mock AuditBackend instance."""
    return Mock(spec=AuditBackend)

@pytest.fixture
def audit_logger_with_mock_backend(mock_backend: Mock) -> AuditLogger:
    """Provides an AuditLogger instance initialized with a mock backend."""
    return AuditLogger(backend=mock_backend)


# --- Test Cases ---
# Obsolete tests related to direct SQLite interaction, file paths,
# connection management, and context manager are removed.

# The following test functions are being redefined or newly added in subsequent steps:
# test_log_prompt, test_log_response, test_log_event_method, test_nullable_fields, test_get_entries

# --- Test Cases ---
# Obsolete tests related to direct SQLite interaction, file paths,
# connection management, and context manager are removed.

# The following test functions are being redefined or newly added in subsequent steps:
# test_log_prompt, test_log_response, test_log_event_method, test_nullable_fields, test_get_entries


# Test data for get_session_entries
ts1 = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
ts2 = datetime(2023, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
ts3 = datetime(2023, 1, 1, 10, 1, 0, tzinfo=timezone.utc) # Out of order for sorting test

# Corrected AuditLogEntry instantiations to include all fields, providing None for optional ones not specifically set.
entry1_sessA = AuditLogEntry(
    id="1", timestamp=ts1, app_name="app", user_name="user", model="model",
    prompt_text="prompt1", response_text=None, remote_completion_id=None, project="projA",
    log_type="prompt", session="sessionA"
)
entry2_sessA = AuditLogEntry(
    id="2", timestamp=ts2, app_name="app", user_name="user", model="model",
    prompt_text=None, response_text="response1", remote_completion_id="cmpl-1", project="projA",
    log_type="response", session="sessionA"
)
entry3_sessB = AuditLogEntry(
    id="3", timestamp=ts1, app_name="app", user_name="user", model="model",
    prompt_text="prompt2", response_text=None, remote_completion_id=None, project="projB",
    log_type="prompt", session="sessionB"
)
entry4_sessA_oos = AuditLogEntry( # Out of order
    id="4", timestamp=ts3, app_name="app", user_name="user", model="model",
    prompt_text="prompt3_oos", response_text=None, remote_completion_id=None, project="projA",
    log_type="prompt", session="sessionA"
)
entry5_no_sess = AuditLogEntry(
    id="5", timestamp=ts1, app_name="app", user_name="user", model="model",
    prompt_text="prompt4_no_sess", response_text=None, remote_completion_id=None, project="projC",
    log_type="prompt", session=None
)


def test_get_session_entries_valid_session_multiple_entries_sorted(audit_logger_with_mock_backend: AuditLogger):
    """Test retrieving multiple entries for a session, ensuring they are sorted."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    mock_backend_instance.get_audit_log_entries.return_value = [
        entry1_sessA, entry3_sessB, entry2_sessA, entry4_sessA_oos, entry5_no_sess
    ]

    session_id = "sessionA"
    result = logger.get_session_entries(session_id)

    assert len(result) == 3
    assert result[0].id == entry1_sessA.id # ts1
    assert result[1].id == entry4_sessA_oos.id # ts3 (sorted before ts2)
    assert result[2].id == entry2_sessA.id # ts2
    assert all(entry.session == session_id for entry in result)
    mock_backend_instance.get_audit_log_entries.assert_called_once()


def test_get_session_entries_valid_session_single_entry(audit_logger_with_mock_backend: AuditLogger):
    """Test retrieving a single entry for a session."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    mock_backend_instance.get_audit_log_entries.return_value = [entry3_sessB, entry5_no_sess]

    session_id = "sessionB"
    result = logger.get_session_entries(session_id)

    assert len(result) == 1
    assert result[0].id == entry3_sessB.id
    assert result[0].session == session_id
    mock_backend_instance.get_audit_log_entries.assert_called_once()


def test_get_session_entries_invalid_session_id(audit_logger_with_mock_backend: AuditLogger):
    """Test retrieving entries for a non-existent session ID raises ValueError."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    mock_backend_instance.get_audit_log_entries.return_value = [entry1_sessA, entry3_sessB]

    session_id = "nonExistentSession"
    with pytest.raises(ValueError, match=f"No audit log entries found for session ID: {session_id}"):
        logger.get_session_entries(session_id)
    mock_backend_instance.get_audit_log_entries.assert_called_once()


def test_get_session_entries_ignores_none_session(audit_logger_with_mock_backend: AuditLogger):
    """Test that entries with session=None are ignored."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    mock_backend_instance.get_audit_log_entries.return_value = [entry1_sessA, entry5_no_sess]

    session_id = "sessionA"
    result = logger.get_session_entries(session_id)

    assert len(result) == 1
    assert result[0].id == entry1_sessA.id
    assert all(entry.session is not None for entry in result)
    mock_backend_instance.get_audit_log_entries.assert_called_once()

def test_get_session_entries_empty_backend_response(audit_logger_with_mock_backend: AuditLogger):
    """Test that ValueError is raised if backend returns no entries at all."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    mock_backend_instance.get_audit_log_entries.return_value = [] # Empty list

    session_id = "anySession"
    with pytest.raises(ValueError, match=f"No audit log entries found for session ID: {session_id}"):
        logger.get_session_entries(session_id)
    mock_backend_instance.get_audit_log_entries.assert_called_once()


def test_log_prompt(audit_logger_with_mock_backend: AuditLogger):
    """Tests the log_prompt method using a mock backend."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    app_name = "test_app_prompt"
    user_name = "test_user_prompt"
    model = "gpt-test-prompt"
    prompt_text = "This is a test prompt."
    project_name = "ProjectAlpha"
    
    # Test with project
    logger.log_prompt(app_name, user_name, model, prompt_text, project=project_name)
    
    mock_backend_instance.log_audit_event.assert_called_once()
    call_args = mock_backend_instance.log_audit_event.call_args
    actual_entry: AuditLogEntry = call_args[0][0]

    assert isinstance(actual_entry, AuditLogEntry)
    assert actual_entry.app_name == app_name
    assert actual_entry.user_name == user_name
    assert actual_entry.model == model
    assert actual_entry.prompt_text == prompt_text
    assert actual_entry.project == project_name
    assert actual_entry.log_type == "prompt"
    assert actual_entry.response_text is None
    assert actual_entry.remote_completion_id is None
    assert actual_entry.id is None # id is generated by backend
    assert isinstance(actual_entry.timestamp, datetime)
    # Check timestamp is recent (e.g., within last 5 seconds)
    assert (datetime.now(timezone.utc) - actual_entry.timestamp) < timedelta(seconds=5)

    # Test without project (project should be None)
    mock_backend_instance.reset_mock() # Reset mock for the next call
    logger.log_prompt(app_name, user_name, model, prompt_text)
    
    mock_backend_instance.log_audit_event.assert_called_once()
    call_args_no_project = mock_backend_instance.log_audit_event.call_args
    actual_entry_no_project: AuditLogEntry = call_args_no_project[0][0]
    assert actual_entry_no_project.project is None


def test_log_response(audit_logger_with_mock_backend: AuditLogger):
    """Tests the log_response method using a mock backend."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    app_name = "test_app_response"
    user_name = "test_user_response"
    model = "gpt-test-response"
    response_text = "This is a test response."
    completion_id = "cmpl-test123"
    project_name = "ProjectBeta"
    custom_timestamp = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    logger.log_response(
        app_name, user_name, model, response_text,
        remote_completion_id=completion_id, project=project_name, timestamp=custom_timestamp
    )

    mock_backend_instance.log_audit_event.assert_called_once()
    call_args = mock_backend_instance.log_audit_event.call_args
    actual_entry: AuditLogEntry = call_args[0][0]

    assert isinstance(actual_entry, AuditLogEntry)
    assert actual_entry.app_name == app_name
    assert actual_entry.user_name == user_name
    assert actual_entry.model == model
    assert actual_entry.response_text == response_text
    assert actual_entry.remote_completion_id == completion_id
    assert actual_entry.project == project_name
    assert actual_entry.log_type == "response"
    assert actual_entry.prompt_text is None
    assert actual_entry.timestamp == custom_timestamp


def test_log_event_method(audit_logger_with_mock_backend: AuditLogger):
    """Tests the generic log_event method using a mock backend."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    app_name = "generic_app"
    user_name = "generic_user"
    model = "generic_model"
    prompt = "generic_prompt"
    response = "generic_response"
    remote_id = "cmpl-generic"
    project_name = "ProjectGamma"
    log_type_custom = "custom_event_type"
    
    logger.log_event(
        app_name=app_name, user_name=user_name, model=model, log_type=log_type_custom,
        prompt_text=prompt, response_text=response, remote_completion_id=remote_id,
        project=project_name
    )

    mock_backend_instance.log_audit_event.assert_called_once()
    call_args = mock_backend_instance.log_audit_event.call_args
    actual_entry: AuditLogEntry = call_args[0][0]

    assert isinstance(actual_entry, AuditLogEntry)
    assert actual_entry.app_name == app_name
    assert actual_entry.user_name == user_name
    assert actual_entry.model == model
    assert actual_entry.prompt_text == prompt
    assert actual_entry.response_text == response
    assert actual_entry.remote_completion_id == remote_id
    assert actual_entry.project == project_name
    assert actual_entry.log_type == log_type_custom
    assert isinstance(actual_entry.timestamp, datetime)


def test_nullable_fields(audit_logger_with_mock_backend: AuditLogger):
    """Tests that nullable fields are correctly passed as None to the backend."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    # Test log_prompt with minimal fields (project=None by default)
    logger.log_prompt("null_app", "null_user", "null_model", "prompt text")
    
    mock_backend_instance.log_audit_event.assert_called_once()
    call_args_prompt = mock_backend_instance.log_audit_event.call_args
    entry_prompt: AuditLogEntry = call_args_prompt[0][0]
    
    assert entry_prompt.project is None
    assert entry_prompt.response_text is None
    assert entry_prompt.remote_completion_id is None

    # Test log_response with minimal fields (project=None, remote_completion_id=None by default)
    mock_backend_instance.reset_mock()
    logger.log_response("null_app", "null_user", "null_model", "response text")

    mock_backend_instance.log_audit_event.assert_called_once()
    call_args_response = mock_backend_instance.log_audit_event.call_args
    entry_response: AuditLogEntry = call_args_response[0][0]

    assert entry_response.project is None
    assert entry_response.prompt_text is None
    assert entry_response.remote_completion_id is None

    # Test log_event with all optional fields as None
    mock_backend_instance.reset_mock()
    logger.log_event(
        app_name="null_event_app", user_name="null_event_user", model="null_event_model",
        log_type="null_type", prompt_text=None, response_text=None,
        remote_completion_id=None, project=None
    )
    mock_backend_instance.log_audit_event.assert_called_once()
    call_args_event = mock_backend_instance.log_audit_event.call_args
    entry_event: AuditLogEntry = call_args_event[0][0]

    assert entry_event.prompt_text is None
    assert entry_event.response_text is None
    assert entry_event.remote_completion_id is None
    assert entry_event.project is None


def test_get_entries(audit_logger_with_mock_backend: AuditLogger):
    """Tests the get_entries method."""
    logger = audit_logger_with_mock_backend
    mock_backend_instance = logger.backend

    start_date_filter = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date_filter = datetime(2023, 1, 31, tzinfo=timezone.utc)
    app_name_filter = "test_app_filter"
    user_name_filter = "test_user_filter"
    project_filter = "ProjectFilter"
    log_type_filter = "prompt_filter"
    limit_filter = 100

    # Configure mock backend return value
    expected_entries = [
        Mock(spec=AuditLogEntry),
        Mock(spec=AuditLogEntry)
    ]
    mock_backend_instance.get_audit_log_entries.return_value = expected_entries

    # Call get_entries with all filters
    actual_result = logger.get_entries(
        start_date=start_date_filter,
        end_date=end_date_filter,
        app_name=app_name_filter,
        user_name=user_name_filter,
        project=project_filter,
        log_type=log_type_filter,
        limit=limit_filter
    )

    # Assert backend method was called correctly
    mock_backend_instance.get_audit_log_entries.assert_called_once_with(
        start_date=start_date_filter,
        end_date=end_date_filter,
        app_name=app_name_filter,
        user_name=user_name_filter,
        project=project_filter,
        log_type=log_type_filter,
        limit=limit_filter
    )

    # Assert the result from get_entries matches the mock's return value
    assert actual_result == expected_entries

    # Test with no filters
    mock_backend_instance.reset_mock()
    mock_backend_instance.get_audit_log_entries.return_value = [] # Reset return value for this call
    
    logger.get_entries()
    mock_backend_instance.get_audit_log_entries.assert_called_once_with(
        start_date=None,
        end_date=None,
        app_name=None,
        user_name=None,
        project=None,
        log_type=None,
        limit=None
    )
