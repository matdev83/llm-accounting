import importlib
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

import llm_accounting.backends.sqlite as sqlite_backend_module
from llm_accounting import backends
from llm_accounting.cli.main import main as cli_main


@patch("llm_accounting.cli.utils.get_accounting")
def test_select_basic_query(mock_get_accounting, test_db, capsys):
    """Test basic SELECT query execution"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.backend.execute_query.return_value = [
        {'model': 'gpt-4', 'prompt_tokens': 100, 'completion_tokens': 50},
        {'model': 'gpt-3.5', 'prompt_tokens': 75, 'completion_tokens': 25}
    ]

    with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT model, prompt_tokens, completion_tokens FROM accounting_entries WHERE username = 'user1'"]):
        cli_main()

    captured = capsys.readouterr()
    assert "gpt-4" in captured.out
    assert "gpt-3.5" in captured.out
    assert "100" in captured.out
    assert "50" in captured.out
    mock_accounting_instance.__exit__.assert_called_once()
