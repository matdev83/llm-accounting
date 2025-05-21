import pytest
from click.testing import CliRunner
import importlib
from llm_accounting.cli import cli as cli_command
from llm_accounting import backends
import llm_accounting.backends.sqlite as sqlite_backend_module

def test_select_output_formatting(test_db, monkeypatch):
    """Test table formatting of results"""
    runner = CliRunner()
    result = runner.invoke(cli_command, [
        "select",
        "--query",
        "SELECT model, username FROM accounting_entries LIMIT 1"
    ])

    assert result.exit_code == 0
    assert "┌───────┬──────────┐" in result.output  # Table borders
    assert "│ model │ username │" in result.output  # Header
    assert "│ gpt-4 │ user1    │" in result.output  # First row
