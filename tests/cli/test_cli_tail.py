import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

from llm_accounting import LLMAccounting
from llm_accounting.cli.main import main as cli_main


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


@patch("llm_accounting.cli.utils.get_accounting")
def test_tail_default(mock_get_accounting, capsys):
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance
    mock_backend_instance.tail.return_value = [
        make_entry(model="gpt-4", prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.002, execution_time=1.5, caller_name="test_app", username="test_user"),
        make_entry(model="gpt-3.5-turbo", prompt_tokens=200, completion_tokens=100, total_tokens=300, cost=0.003, execution_time=2.0)
    ]

    with patch.object(sys, 'argv', ['cli_main', "tail"]):
        cli_main()
    captured = capsys.readouterr()
    assert "Last 2 Usage Entries" in captured.out
    assert "gpt-4" in captured.out
    assert "test" in captured.out
    assert "100" in captured.out
    assert "50" in captured.out
    assert "150" in captured.out
    assert "$0.0" in captured.out
    assert "1.50s" in captured.out
    assert "gpt-3" in captured.out
    assert "-" in captured.out
    assert "200" in captured.out
    assert "100" in captured.out
    assert "300" in captured.out
    assert "$0.0" in captured.out
    assert "2.00s" in captured.out


@patch("llm_accounting.cli.utils.get_accounting")
def test_tail_custom_number(mock_get_accounting, capsys):
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance
    mock_backend_instance.tail.return_value = [
        make_entry(model="gpt-4", prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.002, execution_time=1.5, caller_name="test_app", username="test_user")
    ]

    with patch.object(sys, 'argv', ['cli_main', "tail", "-n", "5"]):
        cli_main()
    captured = capsys.readouterr()
    assert "Last 1 Usage Entry" in captured.out or "Last 1 Usage Entries" in captured.out
    assert "gpt-4" in captured.out
    assert "test" in captured.out
    assert "100" in captured.out
    assert "50" in captured.out
    assert "150" in captured.out
    assert "$0.0" in captured.out
    assert "1.50s" in captured.out


@patch("llm_accounting.cli.utils.get_accounting")
def test_tail_empty(mock_get_accounting, capsys):
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance
    mock_backend_instance.tail.return_value = []

    with patch.object(sys, 'argv', ['cli_main', "tail"]):
        cli_main()
    captured = capsys.readouterr()
    assert "No usage entries found" in captured.out
