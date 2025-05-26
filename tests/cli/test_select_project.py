import sys
import pytest
from unittest.mock import patch, MagicMock
from llm_accounting import LLMAccounting, UsageEntry
from llm_accounting.cli.main import main as cli_main

# Use the same make_entry from test_cli_tail or conftest if it were there
def make_cli_test_entry(**kwargs):
    entry = MagicMock(spec=UsageEntry) # Use spec to ensure it has UsageEntry attributes
    entry.model = kwargs.get("model", "gpt-4")
    entry.prompt_tokens = kwargs.get("prompt_tokens", 0)
    entry.completion_tokens = kwargs.get("completion_tokens", 0)
    entry.total_tokens = kwargs.get("total_tokens", 0)
    entry.cost = kwargs.get("cost", 0.0)
    entry.execution_time = kwargs.get("execution_time", 0.0)
    entry.timestamp = kwargs.get("timestamp", MagicMock()) # Mock timestamp
    entry.timestamp.strftime.return_value = "2024-01-01 12:00:00" # Mock strftime
    entry.caller_name = kwargs.get("caller_name", "")
    entry.username = kwargs.get("username", "")
    entry.project = kwargs.get("project", None)
    entry.cached_tokens = kwargs.get("cached_tokens", 0)
    entry.reasoning_tokens = kwargs.get("reasoning_tokens", 0)
    
    # Make it behave like a dictionary for execute_query results
    # This matches how SQLiteBackend's execute_query returns list[dict]
    # and how NeonBackend's execute_query also returns list[dict]
    # The select command formats these dicts.
    
    # Create a dictionary representation for when this mock entry is part of `execute_query`'s return
    dict_representation = {
        'id': kwargs.get('id', 1), # Assuming an ID for completeness
        'timestamp': entry.timestamp.strftime.return_value,
        'model': entry.model,
        'prompt_tokens': entry.prompt_tokens,
        'completion_tokens': entry.completion_tokens,
        'total_tokens': entry.total_tokens,
        'local_prompt_tokens': kwargs.get('local_prompt_tokens'),
        'local_completion_tokens': kwargs.get('local_completion_tokens'),
        'local_total_tokens': kwargs.get('local_total_tokens'),
        'project': entry.project,
        'cost': entry.cost,
        'execution_time': entry.execution_time,
        'caller_name': entry.caller_name,
        'username': entry.username,
        'cached_tokens': entry.cached_tokens,
        'reasoning_tokens': entry.reasoning_tokens,
    }
    # Allow accessing attributes via dot notation AND as a dictionary
    entry.configure_mock(**dict_representation)

    def getitem_side_effect(key):
        return dict_representation[key]
    entry.__getitem__.side_effect = getitem_side_effect
    entry.keys.return_value = dict_representation.keys()
    entry.values.return_value = dict_representation.values()
    
    return entry


@patch("llm_accounting.cli.utils.get_accounting")
def test_select_no_project_filter_displays_project_column(mock_get_accounting, capsys, sqlite_backend_with_project_data):
    """Test `select` with no project filter shows project column and all entries."""
    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)

    with patch.object(sys, 'argv', ['cli_main', "select"]): # No --query, so should use default SELECT *
        cli_main()
    
    captured = capsys.readouterr().out
    assert "ProjectAlpha" in captured
    assert "ProjectBeta" in captured
    assert "model_no_project" in captured # Entry with project=NULL
    assert "project" in captured.lower() # Check for 'project' column header

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_filter_by_project_name(mock_get_accounting, capsys, sqlite_backend_with_project_data):
    """Test `select --project <name>` filters correctly."""
    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)
    project_to_filter = "ProjectAlpha"

    with patch.object(sys, 'argv', ['cli_main', "select", "--project", project_to_filter]):
        cli_main()
        
    captured = capsys.readouterr().out
    assert project_to_filter in captured
    assert "modelA_alpha" in captured # Belongs to ProjectAlpha
    assert "modelC_alpha" in captured # Belongs to ProjectAlpha
    assert "ProjectBeta" not in captured
    assert "modelB_beta" not in captured
    assert "model_no_project" not in captured

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_filter_by_project_null(mock_get_accounting, capsys, sqlite_backend_with_project_data):
    """Test `select --project NULL` filters for entries with no project."""
    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)

    with patch.object(sys, 'argv', ['cli_main', "select", "--project", "NULL"]):
        cli_main()
        
    captured = capsys.readouterr().out
    assert "model_no_project" in captured # This entry has project=NULL
    assert "ProjectAlpha" not in captured # modelA_alpha and modelC_alpha should not be here
    assert "ProjectBeta" not in captured  # modelB_beta should not be here
    # Check that the project column for the displayed entry shows 'N/A' or similar for None
    # This depends on how run_select formats None values for the table. It was "N/A".
    # A bit hard to assert precisely without parsing the table, but we know "model_no_project" is there.
    # And we can check its project value was indeed NULL from the fixture.
    # The main check is that only "model_no_project" is present.

@pytest.fixture
def sqlite_backend_with_project_data(sqlite_backend):
    """Pre-fill SQLite backend with data including different project values."""
    backend = sqlite_backend
    backend.insert_usage(UsageEntry(model="modelA_alpha", cost=0.1, execution_time=1, project="ProjectAlpha"))
    backend.insert_usage(UsageEntry(model="modelB_beta", cost=0.2, execution_time=1, project="ProjectBeta"))
    backend.insert_usage(UsageEntry(model="modelC_alpha", cost=0.3, execution_time=1, project="ProjectAlpha"))
    backend.insert_usage(UsageEntry(model="model_no_project", cost=0.4, execution_time=1, project=None))
    return backend
