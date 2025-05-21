import os
import sys
from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from llm_accounting import LLMAccounting
from llm_accounting.cli.main import main as cli_main


@patch("llm_accounting.cli.utils.get_accounting")
def test_track_usage(mock_get_accounting):
    """Test tracking a new usage entry"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    with patch.object(sys, 'argv', ['cli_main', "track", "--model", "gpt-3.5-turbo", "--prompt-tokens", "100", "--completion-tokens", "200", "--total-tokens", "300", "--cost", "0.02", "--execution-time", "0.5"]):
        cli_main()

    mock_backend_instance.insert_usage.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_track_usage_with_timestamp(mock_get_accounting):
    """Test tracking a new usage entry with a specific timestamp"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    timestamp = datetime(2023, 10, 1, 12, 0, 0)

    with patch.object(sys, 'argv', ['cli_main', "track", "--model", "gpt-3.5-turbo", "--prompt-tokens", "100", "--completion-tokens", "200", "--total-tokens", "300", "--cost", "0.02", "--execution-time", "0.5", "--timestamp", timestamp.strftime("%Y-%m-%d %H:%M:%S")]):
        cli_main()

    mock_backend_instance.insert_usage.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_track_usage_with_caller_name(mock_get_accounting):
    """Test tracking a new usage entry with a caller name"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    with patch.object(sys, 'argv', ['cli_main', "track", "--model", "gpt-3.5-turbo", "--prompt-tokens", "100", "--completion-tokens", "200", "--total-tokens", "300", "--cost", "0.02", "--execution-time", "0.5", "--caller-name", "test_app"]):
        cli_main()

    mock_backend_instance.insert_usage.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_track_usage_with_username(mock_get_accounting):
    """Test tracking a new usage entry with a username"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    with patch.object(sys, 'argv', ['cli_main', "track", "--model", "gpt-3.5-turbo", "--prompt-tokens", "100", "--completion-tokens", "200", "--total-tokens", "300", "--cost", "0.02", "--execution-time", "0.5", "--username", "test_user"]):
        cli_main()

    mock_backend_instance.insert_usage.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_track_usage_with_cached_tokens(mock_get_accounting):
    """Test tracking a new usage entry with cached tokens"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    with patch.object(sys, 'argv', ['cli_main', "track", "--model", "gpt-3.5-turbo", "--prompt-tokens", "100", "--completion-tokens", "200", "--total-tokens", "300", "--cost", "0.02", "--execution-time", "0.5", "--cached-tokens", "50"]):
        cli_main()

    mock_backend_instance.insert_usage.assert_called_once()


@patch("llm_accounting.cli.utils.get_accounting")
def test_track_usage_with_reasoning_tokens(mock_get_accounting):
    """Test tracking a new usage entry with reasoning tokens"""
    mock_backend_instance = MagicMock()
    real_accounting_instance = LLMAccounting(backend=mock_backend_instance)
    mock_get_accounting.return_value = real_accounting_instance

    with patch.object(sys, 'argv', ['cli_main', "track", "--model", "gpt-3.5-turbo", "--prompt-tokens", "100", "--completion-tokens", "200", "--total-tokens", "300", "--cost", "0.02", "--execution-time", "0.5", "--reasoning-tokens", "50"]):
        cli_main()

    mock_backend_instance.insert_usage.assert_called_once()
