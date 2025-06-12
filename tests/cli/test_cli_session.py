import pytest
import sys
from unittest.mock import patch, MagicMock
from io import StringIO
from datetime import datetime, timezone

from llm_accounting.backends.base import AuditLogEntry
from llm_accounting.cli.main import main as cli_main

# Test data for CLI tests
ts_cli1 = datetime(2023, 2, 1, 11, 0, 0, tzinfo=timezone.utc)
ts_cli2 = datetime(2023, 2, 1, 11, 5, 0, tzinfo=timezone.utc)

cli_entry1_sessX = AuditLogEntry(
    id="cli1", timestamp=ts_cli1, app_name="cli_app", user_name="cli_user",
    model="gpt-cli", log_type="prompt", session="sessionX", prompt_text="Hello model",
    response_text=None, remote_completion_id=None, project="cli_proj" # Added missing fields
)
cli_entry2_sessX = AuditLogEntry(
    id="cli2", timestamp=ts_cli2, app_name="cli_app", user_name="cli_user",
    model="gpt-cli", log_type="response", session="sessionX", response_text="Hello user",
    prompt_text=None, remote_completion_id="cmpl-cli", project="cli_proj" # Added missing fields
)

@pytest.fixture
def mock_accounting_object():
    """Fixture to create a mock accounting object with a mock audit_logger."""
    mock_audit_logger = MagicMock()
    mock_accounting = MagicMock()
    mock_accounting.audit_logger = mock_audit_logger
    # Mock the context manager methods
    mock_accounting.__enter__ = MagicMock(return_value=mock_accounting)
    mock_accounting.__exit__ = MagicMock(return_value=None)
    return mock_accounting

def run_cli_command(args_list, mock_get_accounting_func):
    """Helper function to run the CLI command with patched sys.argv and capturing output."""
    # Prepend 'llm-accounting' as the program name if not already there
    if not args_list or args_list[0] != 'llm-accounting':
        args_list = ['llm-accounting'] + args_list

    with patch.object(sys, 'argv', args_list), \
         patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
         patch('sys.stderr', new_callable=StringIO) as mock_stderr, \
         patch('llm_accounting.cli.utils.get_accounting', mock_get_accounting_func): # Patched where get_accounting is defined

        exit_code = 0
        try:
            cli_main()
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0 # Argparse help exits with 0 by default on success

        return mock_stdout.getvalue(), mock_stderr.getvalue(), exit_code

# Test Case 1: Successful session retrieval
def test_cli_session_success(mock_accounting_object, capsys):
    mock_audit_logger = mock_accounting_object.audit_logger
    mock_audit_logger.get_session_entries.return_value = [cli_entry1_sessX, cli_entry2_sessX]

    # Patch get_accounting where it is defined
    with patch('llm_accounting.cli.utils.get_accounting', return_value=mock_accounting_object) as mock_get_acc:
        # Patch sys.argv and call cli_main directly
        test_session_id = "sessionX"
        original_argv = sys.argv
        sys.argv = ["llm-accounting", "session", test_session_id]

        try:
            cli_main()
        except SystemExit as e:
            assert e.code == 0 # Should exit cleanly
        finally:
            sys.argv = original_argv # Restore original argv

        captured = capsys.readouterr() # Use capsys provided by pytest

    mock_audit_logger.get_session_entries.assert_called_once_with(test_session_id)

    expected_output_parts = [
        f"### [{ts_cli1.isoformat()}] user: cli_user to: gpt-cli, out tokens: <tokens_unavailable>",
        "Hello model",
        f"### [{ts_cli2.isoformat()}] model: gpt-cli to: cli_user, completion tokens: <completion_tokens_unavailable>",
        "Hello user"
    ]
    for part in expected_output_parts:
        assert part in captured.out
    assert captured.err == ""


# Test Case 2: Session ID not found
def test_cli_session_not_found(mock_accounting_object, capsys):
    mock_audit_logger = mock_accounting_object.audit_logger
    error_message = "No audit log entries found for session ID: nonExistentSession"
    mock_audit_logger.get_session_entries.side_effect = ValueError(error_message)

    with patch('llm_accounting.cli.utils.get_accounting', return_value=mock_accounting_object):
        original_argv = sys.argv
        sys.argv = ["llm-accounting", "session", "nonExistentSession"]

        with pytest.raises(SystemExit) as e:
            cli_main()

        assert e.value.code == 1 # Should exit with error code 1
        sys.argv = original_argv

    captured = capsys.readouterr()
    assert f"Error: {error_message}" in captured.out # handle_session_command prints to stdout
    # or captured.err depending on final implementation of error printing

# Test Case 3: CLI called with no session ID
def test_cli_session_no_session_id(capsys):
    # No need to mock get_accounting here as argparse should fail before that
    original_argv = sys.argv
    sys.argv = ["llm-accounting", "session"] # Missing session_id

    with pytest.raises(SystemExit) as e:
        cli_main()

    assert e.value.code == 2 # Argparse error for missing arguments is typically 2
    sys.argv = original_argv

    captured = capsys.readouterr()
    assert "usage: llm-accounting session [-h] session_id" in captured.err
    assert "error: the following arguments are required: session_id" in captured.err

# Test Case 4: Successful session retrieval using the helper
# This test is to refine the helper and ensure it works as expected.
def test_cli_session_success_with_helper(mock_accounting_object):
    mock_audit_logger = mock_accounting_object.audit_logger
    mock_audit_logger.get_session_entries.return_value = [cli_entry1_sessX, cli_entry2_sessX]

    mock_get_accounting = MagicMock(return_value=mock_accounting_object)

    test_session_id = "sessionX"
    stdout, stderr, exit_code = run_cli_command(["session", test_session_id], mock_get_accounting)

    assert exit_code == 0
    mock_audit_logger.get_session_entries.assert_called_once_with(test_session_id)

    expected_output_parts = [
        f"### [{ts_cli1.isoformat()}] user: cli_user to: gpt-cli, out tokens: <tokens_unavailable>",
        "Hello model",
        f"### [{ts_cli2.isoformat()}] model: gpt-cli to: cli_user, completion tokens: <completion_tokens_unavailable>",
        "Hello user"
    ]
    for part in expected_output_parts:
        assert part in stdout
    assert stderr == ""


# Test Case 5: Session ID not found using the helper
def test_cli_session_not_found_with_helper(mock_accounting_object):
    mock_audit_logger = mock_accounting_object.audit_logger
    error_message = "No audit log entries found for session ID: nonExistentSessionHelper"
    mock_audit_logger.get_session_entries.side_effect = ValueError(error_message)

    mock_get_accounting = MagicMock(return_value=mock_accounting_object)

    stdout, stderr, exit_code = run_cli_command(["session", "nonExistentSessionHelper"], mock_get_accounting)

    assert exit_code == 1
    assert f"Error: {error_message}" in stdout # Error printed by handle_session_command
    # assert stderr == "" # Depending on where error is printed. handle_session_command uses print()

# Test Case 6: CLI called with no session ID using the helper
def test_cli_session_no_session_id_with_helper():
    # No need to mock get_accounting here as argparse should fail before that
    mock_get_accounting = MagicMock() # Won't be called

    stdout, stderr, exit_code = run_cli_command(["session"], mock_get_accounting)

    # Argparse error for missing arguments is typically 2.
    # However, if argparse's exit_on_error is False (default in Python 3.9+),
    # it might raise an exception caught by cli_main's generic handler, returning 1.
    # For this test, we expect argparse's own error handling.
    # The helper captures SystemExit(0) from parser.print_help() if command is None,
    # or SystemExit(2) from parser.error().
    assert exit_code == 2
    assert "usage: llm-accounting session [-h] session_id" in stderr
    assert "error: the following arguments are required: session_id" in stderr
    assert stdout == ""
