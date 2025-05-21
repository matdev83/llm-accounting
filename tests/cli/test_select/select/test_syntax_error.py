import pytest
from click.testing import CliRunner
from llm_accounting.cli import cli

def test_select_syntax_error(test_db, monkeypatch):
    """Test handling of SQL syntax errors"""
    monkeypatch.setattr("llm_accounting.backends.get_backend", lambda: test_db)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "select",
        "--query",
        "SELECT model FROM accounting_entries WHERE invalid_syntax"
    ])
    
    assert result.exit_code != 0
    assert "syntax error" in result.output.lower()
