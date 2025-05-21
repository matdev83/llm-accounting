import pytest
from click.testing import CliRunner
from llm_accounting.cli import cli

def test_select_output_formatting(test_db, monkeypatch):
    """Test table formatting of results"""
    monkeypatch.setattr("llm_accounting.backends.get_backend", lambda: test_db)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "select",
        "--query",
        "SELECT model, username FROM accounting_entries LIMIT 1"
    ])
    
    assert result.exit_code == 0
    assert "+--------+---------+" in result.output  # Table borders
    assert "| model  | username |" in result.output  # Header
    assert "| gpt-4  | user1    |" in result.output  # First row
