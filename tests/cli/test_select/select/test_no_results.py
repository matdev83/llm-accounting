import sys
import pytest
from unittest.mock import patch, MagicMock
from llm_accounting import LLMAccounting # For type hinting
from llm_accounting.backends.sqlite import SQLiteBackend # For spec
from llm_accounting.cli.main import main as cli_main
import io
from rich.console import Console

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_no_results(mock_get_accounting_util, test_db): # Removed capsys
    """Test query that returns no results"""
    string_io = io.StringIO()
    test_console = Console(file=string_io)

    mock_backend_instance = test_db
    # Ensure execute_query returns an empty list for this test
    mock_backend_instance.execute_query = MagicMock(return_value=[])

    mock_llm_accounting_instance = MagicMock(spec=LLMAccounting)
    mock_llm_accounting_instance.backend = mock_backend_instance
    mock_llm_accounting_instance.__enter__.return_value = mock_llm_accounting_instance
    mock_llm_accounting_instance.__exit__.return_value = None
    mock_get_accounting_util.return_value = mock_llm_accounting_instance

    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT * FROM accounting_entries WHERE username = 'nonexistent'"]):
            cli_main()

    captured_output = string_io.getvalue()
    assert "No results found" in captured_output
