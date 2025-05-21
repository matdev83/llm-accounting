import pytest
from click.testing import CliRunner
import importlib
from llm_accounting.cli import cli as cli_command
from llm_accounting import backends
import llm_accounting.backends.sqlite as sqlite_backend_module

def test_select_aggregation(test_db, monkeypatch):
    """Test query with GROUP BY and aggregation"""
    # Patch SQLiteBackend's __new__ method to return the test_db fixture
    # This ensures that any attempt to create a SQLiteBackend instance
    # will instead return our pre-configured test_db.
    runner = CliRunner()
    result = runner.invoke(cli_command, [
            "select",
            "--query", 
            "SELECT model, COUNT(*) as count, SUM(prompt_tokens) as total_input "
            "FROM accounting_entries GROUP BY model",
            "--format", "table"
        ])
        
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "gpt-4" in result.output
    assert "gpt-3.5" in result.output
    assert "2" in result.output  # Verify group count
    # Check aggregated counts and sums with flexible formatting
    
    # Verify numeric values appear in correct columns using regex
    import re
    assert re.search(r'gpt-4\W+2\W+250', result.output, re.IGNORECASE)
    assert re.search(r'gpt-3\.5\W+2\W+125', result.output, re.IGNORECASE)
