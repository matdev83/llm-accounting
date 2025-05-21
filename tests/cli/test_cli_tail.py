import pytest
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock
from click.testing import CliRunner

from llm_accounting.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def make_entry(**kwargs):
    entry = MagicMock()
    entry.model = kwargs.get("model", "gpt-4")
    entry.prompt_tokens = kwargs.get("prompt_tokens", 0)
    entry.completion_tokens = kwargs.get("completion_tokens", 0)
    entry.total_tokens = kwargs.get("total_tokens", 0)
    entry.cost = kwargs.get("cost", 0.0)
    entry.execution_time = kwargs.get("execution_time", 0.0)
    entry.timestamp = kwargs.get("timestamp", datetime(2024, 1, 1, 12, 0, 0))
    entry.caller_name = kwargs.get("caller_name", "")
    entry.username = kwargs.get("username", "")
    return entry

@patch("llm_accounting.cli.get_accounting")
def test_tail_default(mock_get_accounting, runner):
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.tail.return_value = [
        make_entry(model="gpt-4", prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.002, execution_time=1.5, caller_name="test_app", username="test_user"),
        make_entry(model="gpt-3.5-turbo", prompt_tokens=200, completion_tokens=100, total_tokens=300, cost=0.003, execution_time=2.0)
    ]

    result = runner.invoke(cli, ["tail"])
    assert result.exit_code == 0
    assert "Last 2 Usage Entries" in result.output
    assert "gpt-4" in result.output
    # Rich may truncate "test_app" and "test_user" to "test_…" or similar, so check for "test"
    assert "test" in result.output
    assert "100" in result.output
    assert "50" in result.output
    assert "150" in result.output
    assert "$0.0" in result.output  # Rich may truncate cost to "$0.0…"
    assert "1.50s" in result.output
    assert "gpt-3" in result.output  # Rich may truncate model name to "gpt-3…"
    assert "-" in result.output
    assert "200" in result.output
    assert "100" in result.output
    assert "300" in result.output
    assert "$0.0" in result.output  # Rich may truncate cost to "$0.0…"
    assert "2.00s" in result.output
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_tail_custom_number(mock_get_accounting, runner):
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.tail.return_value = [
        make_entry(model="gpt-4", prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.002, execution_time=1.5, caller_name="test_app", username="test_user")
    ]

    result = runner.invoke(cli, ["tail", "-n", "5"])
    assert result.exit_code == 0
    assert "Last 1 Usage Entry" in result.output or "Last 1 Usage Entries" in result.output
    assert "gpt-4" in result.output
    # Rich may truncate "test_app" and "test_user" to "test_…" or similar, so check for "test"
    assert "test" in result.output
    assert "100" in result.output
    assert "50" in result.output
    assert "150" in result.output
    assert "$0.0" in result.output  # Rich may truncate cost to "$0.0…"
    assert "1.50s" in result.output
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_tail_empty(mock_get_accounting, runner):
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.tail.return_value = []

    result = runner.invoke(cli, ["tail"])
    assert result.exit_code == 0
    assert "No usage entries found" in result.output
    mock_accounting_instance.__exit__.assert_called_once()
