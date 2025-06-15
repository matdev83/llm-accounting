import sys
import pytest
from unittest.mock import patch, MagicMock
from llm_accounting import LLMAccounting # Keep for type hinting if needed by mocks
from llm_accounting.backends.sqlite import SQLiteBackend # For spec in mock_backend
from llm_accounting.cli.main import main as cli_main
import io
from rich.console import Console

# If make_stats is defined in a shared conftest or helper, it would be imported.
# For this example, let's assume it's available or adapt if necessary.
# from tests.cli.test_cli_stats import make_stats # Example if it were in test_cli_stats

# A simplified make_stats if not available from elsewhere for this standalone change
def make_stats(**kwargs):
    return MagicMock(**kwargs)

@patch("llm_accounting.cli.utils.get_accounting") # Patches where get_accounting is defined and imported by cli_main
def test_select_aggregation(mock_get_accounting_util, test_db): # Removed capsys, added mock_get_accounting
    """Test query with GROUP BY and aggregation"""

    # Setup StringIO and new Console
    string_io = io.StringIO()
    test_console = Console(file=string_io)

    # Mocking the backend that will be used by the LLMAccounting instance
    mock_backend_instance = test_db # Using the test_db fixture which is an initialized SQLiteBackend
    mock_backend_instance.execute_query = MagicMock(return_value=[
        {'model': 'gpt-4', 'count': 2, 'total_input': 250},
        {'model': 'gpt-3.5', 'count': 2, 'total_input': 125}
    ])

    # Configure the mock for get_accounting to return an LLMAccounting instance
    # that uses our specifically mocked backend.
    mock_llm_accounting_instance = MagicMock(spec=LLMAccounting)
    mock_llm_accounting_instance.backend = mock_backend_instance
    mock_llm_accounting_instance.__enter__.return_value = mock_llm_accounting_instance
    mock_llm_accounting_instance.__exit__.return_value = None
    mock_get_accounting_util.return_value = mock_llm_accounting_instance

    # Patch the console used by the select command
    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT model, COUNT(*) as count, SUM(prompt_tokens) as total_input FROM accounting_entries GROUP BY model", "--format", "table"]):
            cli_main()

    captured_output = string_io.getvalue()
    assert "gpt-4" in captured_output
    assert "gpt-3.5" in captured_output
    assert "250" in captured_output
    assert "125" in captured_output
    # Check for table structure elements if possible, e.g., part of the header or a border
    assert "Query Results" in captured_output # Title of the table
    assert "model" in captured_output and "count" in captured_output and "total_input" in captured_output # Headers
