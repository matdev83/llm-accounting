import sys
import pytest
from unittest.mock import patch, MagicMock
from llm_accounting import LLMAccounting # For type hinting
from llm_accounting.backends.sqlite import SQLiteBackend # For spec in mock_backend
from llm_accounting.cli.main import main as cli_main
import io
from rich.console import Console

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_basic_query(mock_get_accounting_util, test_db): # Removed capsys
    """Test basic SELECT query execution"""

    string_io = io.StringIO()
    test_console = Console(file=string_io)

    # The test_db fixture already provides an initialized backend with data
    # We can mock its execute_query if we want to ensure specific results for this test
    mock_backend_instance = test_db
    mock_backend_instance.execute_query = MagicMock(return_value=[
        {'model': 'gpt-4', 'prompt_tokens': 100, 'completion_tokens': 50},
        {'model': 'gpt-3.5', 'prompt_tokens': 75, 'completion_tokens': 25}
    ])

    mock_llm_accounting_instance = MagicMock(spec=LLMAccounting)
    mock_llm_accounting_instance.backend = mock_backend_instance
    mock_llm_accounting_instance.__enter__.return_value = mock_llm_accounting_instance
    mock_llm_accounting_instance.__exit__.return_value = None
    mock_get_accounting_util.return_value = mock_llm_accounting_instance

    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT model, prompt_tokens, completion_tokens FROM accounting_entries WHERE username = 'user1'"]):
            cli_main()

    captured_output = string_io.getvalue()
    assert "gpt-4" in captured_output
    assert "100" in captured_output
    assert "50" in captured_output
    assert "gpt-3.5" in captured_output
    assert "75" in captured_output
    assert "25" in captured_output
    # Check for table structure elements
    assert "Query Results" in captured_output
    assert "model" in captured_output and "prompt_tokens" in captured_output and "completion_tokens" in captured_output
