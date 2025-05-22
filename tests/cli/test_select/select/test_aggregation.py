import importlib
import re
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

import llm_accounting.backends.sqlite as sqlite_backend_module
from llm_accounting import backends
from llm_accounting.cli.main import main as cli_main


@patch("llm_accounting.cli.utils.get_accounting")
def test_select_aggregation(mock_get_accounting, test_db, capsys):
    """Test query with GROUP BY and aggregation"""
    mock_accounting_instance = MagicMock()
    mock_backend_instance = MagicMock()
    mock_accounting_instance.backend = mock_backend_instance
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_backend_instance.execute_query.return_value = [
        {'model': 'gpt-4', 'count': 2, 'total_input': 250},
        {'model': 'gpt-3.5', 'count': 2, 'total_input': 125}
    ]

    with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT model, COUNT(*) as count, SUM(prompt_tokens) as total_input FROM accounting_entries GROUP BY model", "--format", "table"]):
        cli_main()

    captured = capsys.readouterr()
    assert "gpt-4" in captured.out
    assert "gpt-3.5" in captured.out
    assert "2" in captured.out  # Verify group count

    assert re.search(r'gpt-4\W+2\W+250', captured.out, re.IGNORECASE)
    assert re.search(r'gpt-3\.5\W+2\W+125', captured.out, re.IGNORECASE)
    mock_accounting_instance.__exit__.assert_called_once()
