import sys
import pytest
from unittest.mock import patch, MagicMock
from llm_accounting import LLMAccounting # For type hinting
from llm_accounting.backends.sqlite import SQLiteBackend # For spec
from llm_accounting.cli.main import main as cli_main
import io
from rich.console import Console

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_non_select_query(mock_get_accounting_util, test_db): # Removed capsys
    """Test rejection of non-SELECT queries"""
    string_io = io.StringIO()
    test_console = Console(file=string_io)

    # Backend needs to raise ValueError for non-SELECT for this test
    mock_backend_instance = test_db
    mock_backend_instance.execute_query = MagicMock(side_effect=ValueError("Only SELECT queries are allowed"))

    mock_llm_accounting_instance = MagicMock(spec=LLMAccounting)
    mock_llm_accounting_instance.backend = mock_backend_instance
    mock_llm_accounting_instance.__enter__.return_value = mock_llm_accounting_instance
    mock_llm_accounting_instance.__exit__.return_value = None
    mock_get_accounting_util.return_value = mock_llm_accounting_instance

    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--query", "INSERT INTO accounting_entries (model) VALUES ('gpt-4')"]):
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                cli_main()

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1

    captured_output = string_io.getvalue()
    assert "Error executing query: Only SELECT queries are allowed" in captured_output
