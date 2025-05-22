import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from llm_accounting.cli.main import main as cli_main


@patch("llm_accounting.cli.utils.get_accounting")
def test_select_output_formatting(mock_get_accounting, test_db, capsys):
    """Test table formatting of results"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.backend.execute_query.return_value = [
        {'model': 'gpt-4', 'username': 'user1'}
    ]

    with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT model, username FROM accounting_entries LIMIT 1"]):
        with pytest.raises(SystemExit):
            cli_main()
        
    captured = capsys.readouterr()
    assert "Error: Arbitrary SQL queries are no longer supported for security reasons" in captured.out
    mock_accounting_instance.__exit__.assert_called_once()
