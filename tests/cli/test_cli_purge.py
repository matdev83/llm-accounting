import sys
from io import StringIO
from unittest.mock import MagicMock, patch

from llm_accounting import LLMAccounting
from llm_accounting.cli.main import main as cli_main


@patch("llm_accounting.cli.utils.get_accounting")
def test_purge_with_confirmation(mock_get_accounting):
    """Test purge command with confirmation by checking accounting calls"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    # Simulate user input 'y'
    with patch('sys.stdin', StringIO('y\n')), patch.object(sys, 'argv', ['cli_main', 'purge']):
        cli_main()

    mock_backend_instance.purge.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_purge_without_confirmation(mock_get_accounting):
    """Test purge command without confirmation"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    # Simulate user input 'n'
    with patch('sys.stdin', StringIO('n\n')), patch.object(sys, 'argv', ['cli_main', 'purge']):
        cli_main()

    mock_backend_instance.purge.assert_not_called()


@patch("llm_accounting.cli.utils.get_accounting")
def test_purge_with_yes_flag(mock_get_accounting):
    """Test purge command with -y flag by checking accounting calls"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    with patch.object(sys, 'argv', ['cli_main', 'purge', '-y']):
        cli_main()

    mock_backend_instance.purge.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_purge_with_yes_flag_long(mock_get_accounting):
    """Test purge command with --yes flag by checking accounting calls"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    with patch.object(sys, 'argv', ['cli_main', 'purge', '--yes']):
        cli_main()

    mock_backend_instance.purge.assert_called_once()
