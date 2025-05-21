import pytest
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock
from click.testing import CliRunner

from llm_accounting.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

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

@patch("llm_accounting.cli.LLMAccounting")
def test_stats_no_period(mock_llm, runner):
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code != 0
    assert "Please specify a time period" in result.output

@patch("llm_accounting.cli.get_accounting")
@pytest.mark.parametrize("period_args, expected_title", [
    (["--period", "daily"], "Daily Stats"),
    (["--period", "weekly"], "Weekly Stats"),
    (["--period", "monthly"], "Monthly Stats"),
    (["--period", "yearly"], "Yearly Stats"),
])
def test_stats_periods(mock_get_accounting, runner, period_args, expected_title):
    # Setup context manager for LLMAccounting
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.get_period_stats.return_value = make_stats(sum_prompt_tokens=123, sum_cost=1.23)
    mock_accounting_instance.get_model_stats.return_value = [
        ("mock-model-1", make_stats(sum_prompt_tokens=50, sum_cost=0.5)),
        ("mock-model-2", make_stats(sum_prompt_tokens=73, sum_cost=0.73)),
    ]
    mock_accounting_instance.get_model_rankings.return_value = {
        'prompt_tokens': [("mock-model-1", 50.0), ("mock-model-2", 73.0)],
        'cost': [("mock-model-1", 0.5), ("mock-model-2", 0.73)],
    }

    result = runner.invoke(cli, ["stats"] + period_args)
    print("Exception:", result.exception)
    print("Exc info:", result.exc_info)
    assert result.exit_code == 0
    assert expected_title in result.output
    assert "123" in result.output
    assert "$1.2300" in result.output
    mock_accounting_instance.__exit__.assert_called_once()


@patch("llm_accounting.cli.get_accounting")
def test_stats_custom_period(mock_get_accounting, runner):
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None
    mock_accounting_instance.get_period_stats.return_value = make_stats(sum_prompt_tokens=10, sum_cost=0.5)
    mock_accounting_instance.get_model_stats.return_value = [
        ("mock-model-A", make_stats(sum_prompt_tokens=10, sum_cost=0.5)),
    ]
    mock_accounting_instance.get_model_rankings.return_value = {
        'prompt_tokens': [("mock-model-A", 10.0)],
        'cost': [("mock-model-A", 0.5)],
    }

    result = runner.invoke(cli, [
        "stats", "--start", "2024-01-01", "--end", "2024-01-31"
    ])
    assert result.exit_code == 0
    assert "Custom Stats" in result.output
    assert "10" in result.output
    assert "$0.5000" in result.output
    mock_accounting_instance.__exit__.assert_called_once()

def test_custom_db_file_usage(runner):
    import os
    from pathlib import Path

    with runner.isolated_filesystem():
        db_path = "custom_test_db.sqlite"
        # Track a usage entry
        result_track = runner.invoke(cli, [
            "--db-file", db_path,
            "track",
            "--model", "test-model",
            "--cost", "1.23",
            "--execution-time", "2.34"
        ])
        assert result_track.exit_code == 0
        assert "Usage entry tracked successfully" in result_track.output

        # Stats should show the entry
        result_stats = runner.invoke(cli, [
            "--db-file", db_path,
            "stats", "--period", "daily"
        ])
        assert result_stats.exit_code == 0
        assert "Daily Stats" in result_stats.output
        assert "test-model" in result_stats.output

        # The custom db file should exist
        assert Path(db_path).exists()

def test_default_db_file_usage(runner):
    import os
    from pathlib import Path

    with runner.isolated_filesystem():
        # Ensure default db file does not exist initially
        default_db_path = Path("data/accounting.sqlite")
        assert not default_db_path.exists()

        # Track a usage entry without specifying --db-file
        result_track = runner.invoke(cli, [
            "track",
            "--model", "default-model",
            "--cost", "1.00",
            "--execution-time", "1.00"
        ])
        assert result_track.exit_code == 0
        assert "Usage entry tracked successfully" in result_track.output

        # The default db file should now exist
        assert default_db_path.exists()

        # Stats should show the entry from the default db
        result_stats = runner.invoke(cli, [
            "stats", "--period", "daily"
        ])
        assert result_stats.exit_code == 0
        assert "Daily Stats" in result_stats.output
        assert "default-model" in result_stats.output

@patch("llm_accounting.cli.SQLiteBackend")
def test_db_file_validation_error(mock_sqlite_backend, runner):
    # Simulate a ValueError during backend initialization
    mock_sqlite_backend.side_effect = ValueError("Invalid database filename")

    result = runner.invoke(cli, [
        "--db-file", "invalid.txt",
        "stats", "--period", "daily"
    ])
    assert result.exit_code != 0
    assert "Error initializing database (ValueError): Invalid database filename" in result.output

@patch("llm_accounting.cli.SQLiteBackend")
def test_db_file_permission_error(mock_sqlite_backend, runner):
    # Simulate a PermissionError during backend initialization
    mock_sqlite_backend.side_effect = PermissionError("Access to protected path")

    result = runner.invoke(cli, [
        "--db-file", "C:/Windows/protected.db",
        "stats", "--period", "daily"
    ])
    assert result.exit_code != 0
    assert "Error initializing database (PermissionError): Access to protected path" in result.output
