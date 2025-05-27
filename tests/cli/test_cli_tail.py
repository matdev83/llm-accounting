import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

from llm_accounting import LLMAccounting
from llm_accounting.cli.main import main as cli_main
from llm_accounting.cli.utils import format_tokens, format_float, format_time # For verifying formatted output


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
    entry.project = kwargs.get("project", None)
    return entry


@patch("llm_accounting.cli.utils.get_accounting")
def test_tail_default(mock_get_accounting, capsys):
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance
    
    entry1_data = {"model":"gpt-4", "prompt_tokens":100, "completion_tokens":50, "total_tokens":150, "cost":0.002, "execution_time":1.5, "caller_name":"test_application_long_name", "username":"test_user_long_name", "project":None}
    entry2_data = {"model":"gpt-3.5-turbo", "prompt_tokens":200, "completion_tokens":100, "total_tokens":300, "cost":0.003, "execution_time":2.0, "project":"TestProjectLongName"} # Made project name longer
    
    mock_backend_instance.tail.return_value = [
        make_entry(**entry1_data),
        make_entry(**entry2_data)
    ]

    with patch.object(sys, 'argv', ['cli_main', "tail"]):
        cli_main()
    captured = capsys.readouterr().out
    
    assert "Last 2 Usage Entries" in captured
    
    # Check for entry1 data
    assert "gpt-4" in captured # gpt-4 is short enough
    assert "test…" in captured 
    assert format_tokens(entry1_data["prompt_tokens"]) in captured
    assert format_tokens(entry1_data["completion_tokens"]) in captured
    assert format_tokens(entry1_data["total_tokens"]) in captured
    assert "$0.0…" in captured 
    assert "1.5…" in captured 
    assert "│ -         │" in captured or "│ -          │" in captured or "│ -     │" in captured # Project is None

    # Check for entry2 data
    assert "gpt-…" in captured # gpt-3.5-turbo will be truncated
    assert format_tokens(entry2_data["prompt_tokens"]) in captured
    assert format_tokens(entry2_data["completion_tokens"]) in captured
    assert format_tokens(entry2_data["total_tokens"]) in captured
    assert "$0.0…" in captured 
    assert "2.0…" in captured 
    assert "Test…" in captured # Truncated project name "TestProjectLongName"


@patch("llm_accounting.cli.utils.get_accounting")
def test_tail_custom_number(mock_get_accounting, capsys):
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance
    
    entry_data = {"model":"gpt-4", "prompt_tokens":100, "completion_tokens":50, "total_tokens":150, "cost":0.002, "execution_time":1.5, "caller_name":"test_application_long_name", "username":"test_user_long_name", "project":"MyProject"}
    mock_backend_instance.tail.return_value = [
        make_entry(**entry_data)
    ]

    with patch.object(sys, 'argv', ['cli_main', "tail", "-n", "5"]):
        cli_main()
    captured = capsys.readouterr().out
    
    assert "Last 1 Usage Entry" in captured or "Last 1 Usage Entries" in captured
    assert "gpt-4" in captured
    assert "test…" in captured 
    assert format_tokens(entry_data["prompt_tokens"]) in captured
    assert format_tokens(entry_data["completion_tokens"]) in captured
    assert format_tokens(entry_data["total_tokens"]) in captured
    assert "$0.0…" in captured 
    assert "1.5…" in captured 
    assert "MyPr…" in captured or "MyProject" in captured # Handle potential truncation for MyProject


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
