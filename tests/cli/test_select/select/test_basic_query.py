import pytest
from click.testing import CliRunner
from llm_accounting.cli import cli

def test_select_basic_query(test_db, monkeypatch):
    """Test basic SELECT query execution"""
    monkeypatch.setattr("llm_accounting.backends.get_backend", lambda: test_db)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "select",
        "--query",
        "SELECT model, prompt_tokens, completion_tokens FROM accounting_entries WHERE username = 'user1'"
    ])
    
    assert result.exit_code == 0
    assert "gpt-4" in result.output
    assert "gpt-3.5" in result.output
    assert "100" in result.output
    assert "50" in result.output
