import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from llm_accounting.cli.main import main as cli_main


@patch("llm_accounting.cli.utils.get_accounting")
def test_select_no_results(mock_get_accounting, test_db, capsys):
    """Test query that returns no results"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.backend.execute_query.return_value = []

    with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT * FROM accounting_entries WHERE username = 'nonexistent'"]):
        cli_main()

    captured = capsys.readouterr()
    assert "No results found" in captured.out
    mock_accounting_instance.__exit__.assert_called_once()
