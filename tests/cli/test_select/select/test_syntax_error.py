import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from llm_accounting import LLMAccounting
from llm_accounting.cli.main import main as cli_main


@patch("llm_accounting.cli.utils.get_accounting")
def test_select_syntax_error(mock_get_accounting, test_db, capsys):
    """Test handling of SQL syntax errors"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance
    mock_backend_instance.execute_query.side_effect = Exception("no such column: invalid_syntax")

    with patch.object(sys, 'argv', ['cli_main', "select", "--query", "SELECT model FROM accounting_entries WHERE invalid_syntax"]):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            cli_main()

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    captured = capsys.readouterr()
    assert "no such column: invalid_syntax" in captured.out.lower()
