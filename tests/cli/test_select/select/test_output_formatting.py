import sys
import pytest
from unittest.mock import patch, MagicMock
from llm_accounting import LLMAccounting # For type hinting
from llm_accounting.backends.sqlite import SQLiteBackend # For spec
from llm_accounting.cli.main import main as cli_main
import io
from rich.console import Console

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_output_formatting(mock_get_accounting_util, test_db): # Removed capsys
    """Test table formatting of results"""
    string_io = io.StringIO()
    test_console = Console(file=string_io)

    mock_backend_instance = test_db
    mock_backend_instance.execute_query = MagicMock(return_value=[
        {'model': 'gpt-4', 'username': 'user1'}
    ])

    mock_llm_accounting_instance = MagicMock(spec=LLMAccounting)
    mock_llm_accounting_instance.backend = mock_backend_instance
    mock_llm_accounting_instance.__enter__.return_value = mock_llm_accounting_instance
    mock_llm_accounting_instance.__exit__.return_value = None
    mock_get_accounting_util.return_value = mock_llm_accounting_instance

    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT model, username FROM accounting_entries LIMIT 1"]): # Default format is table
            cli_main()

    captured_output = string_io.getvalue()
    assert "model" in captured_output
    assert "username" in captured_output
    assert "gpt-4" in captured_output
    assert "user1" in captured_output
    assert "Query Results" in captured_output # Table title
    # Check for Rich table specific characters if needed, e.g., "┏", "┃", "┗"
    assert "┌" in captured_output # A character indicating Rich table rendering
