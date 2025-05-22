import sys
from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, Mock, patch

import pytest

from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.cli.main import main as cli_main


def make_stats(**kwargs):
    # Minimal UsageStats mock
    stats = MagicMock()
    stats.sum_prompt_tokens = kwargs.get("sum_prompt_tokens", 0)
    stats.sum_completion_tokens = kwargs.get("sum_completion_tokens", 0)
    stats.sum_total_tokens = kwargs.get("sum_total_tokens", 0)
    stats.sum_cost = kwargs.get("sum_cost", 0.0)
    stats.sum_execution_time = kwargs.get("sum_execution_time", 0.0)
    stats.avg_prompt_tokens = kwargs.get("avg_prompt_tokens", 0)
    stats.avg_completion_tokens = kwargs.get("avg_completion_tokens", 0)
    stats.avg_total_tokens = kwargs.get("avg_total_tokens", 0)
    stats.avg_cost = kwargs.get("avg_cost", 0.0)
    stats.avg_execution_time = kwargs.get("avg_execution_time", 0.0)
    return stats


@patch("llm_accounting.cli.utils.get_accounting")
def test_stats_no_period(mock_get_accounting):
    with patch.object(sys, 'argv', ['cli_main', "stats"]):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            cli_main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1  # Expect exit code 1 for error


@patch("llm_accounting.cli.utils.get_accounting")
@pytest.mark.parametrize("period_args, expected_title", [
    (["--period", "daily"], "Daily Stats"),
    (["--period", "weekly"], "Weekly Stats"),
    (["--period", "monthly"], "Monthly Stats"),
    (["--period", "yearly"], "Yearly Stats"),
])
def test_stats_periods(mock_get_accounting, period_args, expected_title, capsys):
    # Setup context manager for LLMAccounting
    mock_accounting_instance = MagicMock()
    mock_backend_instance = MagicMock()
    mock_accounting_instance.backend = mock_backend_instance
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_backend_instance.get_period_stats.return_value = make_stats(sum_prompt_tokens=123, sum_cost=1.23)
    mock_backend_instance.get_model_stats.return_value = [
        ("mock-model-1", make_stats(sum_prompt_tokens=50, sum_cost=0.5)),
        ("mock-model-2", make_stats(sum_prompt_tokens=73, sum_cost=0.73)),
    ]
    mock_backend_instance.get_model_rankings.return_value = {
        'prompt_tokens': [("mock-model-1", 50.0), ("mock-model-2", 73.0)],
        'cost': [("mock-model-1", 0.5), ("mock-model-2", 0.73)],
    }

    with patch.object(sys, 'argv', ['cli_main', "stats"] + period_args):
        cli_main()
    captured = capsys.readouterr()
    assert expected_title in captured.out
    assert "123" in captured.out
    assert "$1.2300" in captured.out
    mock_accounting_instance.__exit__.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_stats_custom_period(mock_get_accounting, capsys):
    mock_accounting_instance = MagicMock()
    mock_backend_instance = MagicMock()
    mock_accounting_instance.backend = mock_backend_instance
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_backend_instance.get_period_stats.return_value = make_stats(sum_prompt_tokens=10, sum_cost=0.5)
    mock_backend_instance.get_model_stats.return_value = [
        ("mock-model-A", make_stats(sum_prompt_tokens=10, sum_cost=0.5)),
    ]
    mock_backend_instance.get_model_rankings.return_value = {
        'prompt_tokens': [("mock-model-A", 10.0)],
        'cost': [("mock-model-A", 0.5)],
    }

    with patch.object(sys, 'argv', ['cli_main', "stats", "--start", "2024-01-01", "--end", "2024-01-31"]):
        cli_main()
    captured = capsys.readouterr()
    assert "Custom Stats" in captured.out
    assert "10" in captured.out
    assert "$0.5000" in captured.out
    mock_accounting_instance.__exit__.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_custom_db_file_usage(mock_get_accounting, capsys):
    mock_accounting_instance = MagicMock()
    mock_backend_instance = MagicMock()
    mock_accounting_instance.backend = mock_backend_instance
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_backend_instance.get_period_stats.return_value = make_stats(sum_prompt_tokens=123, sum_cost=1.23)
    mock_backend_instance.get_model_stats.return_value = []
    mock_backend_instance.get_model_rankings.return_value = {}

    with patch.object(sys, 'argv', ['cli_main', "--db-file", "custom_test_db.sqlite", "stats", "--period", "daily"]):
        cli_main()
    captured = capsys.readouterr()
    assert "Daily Stats" in captured.out
    assert "123" in captured.out
    assert "$1.2300" in captured.out
    mock_get_accounting.assert_called_once_with(db_backend="sqlite", db_file="custom_test_db.sqlite", neon_connection_string=None)
    mock_accounting_instance.__exit__.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_default_db_file_usage(mock_get_accounting, capsys):
    mock_accounting_instance = MagicMock()
    mock_backend_instance = MagicMock()
    mock_accounting_instance.backend = mock_backend_instance
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_backend_instance.get_period_stats.return_value = make_stats(sum_prompt_tokens=123, sum_cost=1.23)
    mock_backend_instance.get_model_stats.return_value = []
    mock_backend_instance.get_model_rankings.return_value = {}

    with patch.object(sys, 'argv', ['cli_main', "stats", "--period", "daily"]):
        cli_main()
    captured = capsys.readouterr()
    assert "Daily Stats" in captured.out
    assert "123" in captured.out
    assert "$1.2300" in captured.out
    mock_get_accounting.assert_called_once_with(db_backend="sqlite", db_file=None, neon_connection_string=None)
    mock_accounting_instance.__exit__.assert_called_once()


@patch("llm_accounting.cli.utils.SQLiteBackend")
def test_db_file_validation_error(mock_sqlite_backend, capsys):
    mock_sqlite_backend.side_effect = ValueError("Invalid database filename")

    with patch.object(sys, 'argv', ['cli_main', "--db-file", "invalid.txt", "stats", "--period", "daily"]):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            cli_main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Invalid database filename" in captured.out


@patch("llm_accounting.cli.utils.SQLiteBackend")
def test_db_file_permission_error(mock_sqlite_backend, capsys):
    mock_sqlite_backend.side_effect = PermissionError("Access to protected path")

    with patch.object(sys, 'argv', ['cli_main', "--db-file", "C:/Windows/protected.db", "stats", "--period", "daily"]):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            cli_main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Access to protected path" in captured.out
