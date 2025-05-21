import pytest
from click.testing import CliRunner
from llm_accounting.cli import cli

def test_select_no_results(test_db, monkeypatch):
    """Test query that returns no results"""
    monkeypatch.setattr("llm_accounting.backends.get_backend", lambda: test_db)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "select",
        "--query",
        "SELECT * FROM accounting_entries WHERE username = 'nonexistent'"
    ])
    
    assert result.exit_code == 0
    assert "No results found" in result.output
