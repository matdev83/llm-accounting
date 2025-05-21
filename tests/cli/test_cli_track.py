import pytest
import os
from datetime import datetime
from click.testing import CliRunner
from llm_accounting.cli import cli
from unittest.mock import patch, MagicMock

@pytest.fixture
def runner():
    return CliRunner()

def test_track_usage_with_protected_db_file(runner):
    """Test tracking usage with a protected database file path"""
    pytest.skip("Skipping due to platform-specific permission issues - use mock_backend fixture instead")

@patch("llm_accounting.cli.get_accounting")
def test_track_usage(mock_get_accounting, runner):
    """Test tracking a new usage entry"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(
        cli,
            [
                "track",
                "--model", "gpt-3.5-turbo",
                "--prompt-tokens", "100",
                "--completion-tokens", "200",
                "--total-tokens", "300",
                "--cost", "0.02",
                "--execution-time", "0.5"
            ]
    )

    assert result.exit_code == 0
    assert "Usage entry tracked successfully" in result.output
    mock_accounting_instance.track_usage.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_track_usage_with_timestamp(mock_get_accounting, runner):
    """Test tracking a new usage entry with a specific timestamp"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    timestamp = datetime(2023, 10, 1, 12, 0, 0)

    result = runner.invoke(
        cli,
        [
            "track",
            "--model", "gpt-3.5-turbo",
            "--prompt-tokens", "100",
            "--completion-tokens", "200",
            "--total-tokens", "300",
            "--cost", "0.02",
            "--execution-time", "0.5",
            "--timestamp", timestamp.isoformat()
        ]
    )

    assert result.exit_code == 0
    assert "Usage entry tracked successfully" in result.output
    mock_accounting_instance.track_usage.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_track_usage_with_caller_name(mock_get_accounting, runner):
    """Test tracking a new usage entry with a caller name"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(
        cli,
        [
            "track",
            "--model", "gpt-3.5-turbo",
            "--prompt-tokens", "100",
            "--completion-tokens", "200",
            "--total-tokens", "300",
            "--cost", "0.02",
            "--execution-time", "0.5",
            "--caller-name", "test_app"
        ]
    )

    assert result.exit_code == 0
    assert "Usage entry tracked successfully" in result.output
    mock_accounting_instance.track_usage.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_track_usage_with_username(mock_get_accounting, runner):
    """Test tracking a new usage entry with a username"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(
        cli,
        [
            "track",
            "--model", "gpt-3.5-turbo",
            "--prompt-tokens", "100",
            "--completion-tokens", "200",
            "--total-tokens", "300",
            "--cost", "0.02",
            "--execution-time", "0.5",
            "--username", "test_user"
        ]
    )

    assert result.exit_code == 0
    assert "Usage entry tracked successfully" in result.output
    mock_accounting_instance.track_usage.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_track_usage_with_cached_tokens(mock_get_accounting, runner):
    """Test tracking a new usage entry with cached tokens"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(
        cli,
        [
            "track",
            "--model", "gpt-3.5-turbo",
            "--prompt-tokens", "100",
            "--completion-tokens", "200",
            "--total-tokens", "300",
            "--cost", "0.02",
            "--execution-time", "0.5",
            "--cached-tokens", "50"
        ]
    )

    assert result.exit_code == 0
    assert "Usage entry tracked successfully" in result.output
    mock_accounting_instance.track_usage.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()

@patch("llm_accounting.cli.get_accounting")
def test_track_usage_with_reasoning_tokens(mock_get_accounting, runner):
    """Test tracking a new usage entry with reasoning tokens"""
    mock_accounting_instance = MagicMock()
    mock_get_accounting.return_value = mock_accounting_instance
    mock_accounting_instance.__enter__.return_value = mock_accounting_instance
    mock_accounting_instance.__exit__.return_value = None

    result = runner.invoke(
        cli,
        [
            "track",
            "--model", "gpt-3.5-turbo",
            "--prompt-tokens", "100",
            "--completion-tokens", "200",
            "--total-tokens", "300",
            "--cost", "0.02",
            "--execution-time", "0.5",
            "--reasoning-tokens", "50"
        ]
    )

    assert result.exit_code == 0
    assert "Usage entry tracked successfully" in result.output
    mock_accounting_instance.track_usage.assert_called_once()
    mock_accounting_instance.__exit__.assert_called_once()
