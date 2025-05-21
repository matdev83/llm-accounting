import pytest
from click.testing import CliRunner
from llm_accounting.cli import cli

def test_select_non_select_query(test_db, monkeypatch):
    """Test rejection of non-SELECT queries"""
    monkeypatch.setattr("llm_accounting.backends.get_backend", lambda: test_db)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "select",
        "--query",
        "INSERT INTO accounting_entries (model) VALUES ('gpt-4')"
    ])
    
    assert result.exit_code != 0
    assert "Only SELECT queries are allowed" in result.output
