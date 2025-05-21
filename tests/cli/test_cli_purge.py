import pytest
from unittest.mock import patch, Mock, MagicMock

from llm_accounting.cli import cli

@pytest.fixture
def runner():
    from click.testing import CliRunner
    return CliRunner()

from unittest.mock import patch, Mock

@patch("llm_accounting.cli.get_accounting")
def test_purge_with_confirmation(mock_get_accounting, runner):
    """Test purge command with confirmation by checking accounting calls"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None # Ensure __exit__ returns None

    result = runner.invoke(cli, ["purge"], input="y\n")
    assert result.exit_code == 0
    mock_accounting_instance.purge.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_purge_without_confirmation(mock_get_accounting, runner):
    """Test purge command without confirmation"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(cli, ["purge"], input="n\n")
    assert result.exit_code == 0
    mock_accounting_instance.purge.assert_not_called()
    mock_accounting_instance.__exit__.assert_not_called() # Should not exit if cancelled

@patch("llm_accounting.cli.get_accounting")
def test_purge_with_yes_flag(mock_get_accounting, runner):
    """Test purge command with -y flag by checking accounting calls"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(cli, ["purge", "-y"])
    assert result.exit_code == 0
    mock_accounting_instance.purge.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_purge_with_yes_flag_long(mock_get_accounting, runner):
    """Test purge command with --yes flag by checking accounting calls"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(cli, ["purge", "--yes"])
    assert result.exit_code == 0
    mock_accounting_instance.purge.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()
