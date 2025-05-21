import pytest
from click.testing import CliRunner
from llm_accounting.cli import cli

def test_select_aggregation(test_db, monkeypatch):
    """Test query with GROUP BY and aggregation"""
    monkeypatch.setattr("llm_accounting.backends.get_backend", lambda: test_db)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "select",
        "--query",
        "SELECT model, COUNT(*) as count, SUM(prompt_tokens) as total_input "
        "FROM accounting_entries GROUP BY model"
    ])
    
    assert result.exit_code == 0
    assert "gpt-4 | 2 | 250" in result.output.replace(" ", "")
    assert "gpt-3.5 | 2 | 125" in result.output.replace(" ", "")
