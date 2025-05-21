import pytest
from click.testing import CliRunner
import importlib
from llm_accounting.cli import cli as cli_command
from llm_accounting import backends
import llm_accounting.backends.sqlite as sqlite_backend_module

def test_select_basic_query(test_db, monkeypatch):
    """Test basic SELECT query execution"""
    runner = CliRunner()
    result = runner.invoke(cli_command, [
        "select",
        "--query",
        "SELECT model, prompt_tokens, completion_tokens FROM accounting_entries WHERE username = 'user1'"
    ])
    
    assert result.exit_code == 0
    assert "gpt-4" in result.output
    assert "gpt-3.5" in result.output
    assert "100" in result.output
    assert "50" in result.output
