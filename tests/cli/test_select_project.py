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
    # and how PostgreSQLBackend's execute_query also returns list[dict]
    # The select command formats these dicts.
    
    # Create a dictionary representation for when this mock entry is part of `execute_query`'s return
    dict_representation = {
        'id': kwargs.get('id', 1), # Assuming an ID for completeness
        'timestamp': entry.timestamp.strftime.return_value,
        'model': entry.model,
        'prompt_tokens': entry.prompt_tokens,
        'completion_tokens': entry.completion_tokens,
        'total_tokens': entry.total_tokens,
        'local_prompt_tokens': kwargs.get('local_prompt_tokens', 0),
        'local_completion_tokens': kwargs.get('local_completion_tokens', 0),
        'local_total_tokens': kwargs.get('local_total_tokens', 0),
        'project': entry.project if entry.project is not None else "", # Ensure project is empty string if None
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

    with patch.object(sys, 'argv', ['cli_main', "select", "--format", "csv"]): # Use CSV format for predictable output
        cli_main()
    
    captured = capsys.readouterr().out.strip().splitlines() # Get lines of CSV output

    # Expected CSV header (order might vary, but these columns should be present)
    header = captured[0].split(',')
    assert "id" in header
    assert "model" in header
    assert "project" in header
    assert "cost" in header

    # Expected data rows (order might vary, so check for presence of key elements)
    # id,timestamp,model,prompt_tokens,completion_tokens,total_tokens,local_prompt_tokens,local_completion_tokens,local_total_tokens,project,cost,execution_time,caller_name,username,cached_tokens,reasoning_tokens
    
    # Entry 1: modelA_alpha, ProjectAlpha
    assert any("modelA_alpha" in line and "ProjectAlpha" in line for line in captured) # Check for project name
    # Entry 2: modelB_beta, ProjectBeta
    assert any("modelB_beta" in line and "ProjectBeta" in line for line in captured)
    # Entry 3: modelC_alpha, ProjectAlpha
    assert any("modelC_alpha" in line and "ProjectAlpha" in line for line in captured)
    # Entry 4: model_no_project, None (empty string in CSV)
    assert any("model_no_project" in line and ",0.4," in line and ",," in line for line in captured) # Project is empty string in CSV

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_filter_by_project_name(mock_get_accounting, capsys, sqlite_backend_with_project_data):
    """Test `select --project <name>` filters correctly."""
    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)
    project_to_filter = "ProjectAlpha"

    with patch.object(sys, 'argv', ['cli_main', "select", "--project", project_to_filter, "--format", "csv"]):
        cli_main()
        
    captured = capsys.readouterr().out.strip().splitlines()

    # Expected CSV header
    header = captured[0].split(',')
    assert "id" in header
    assert "model" in header
    assert "project" in header

    # Check for ProjectAlpha entries
    assert any("modelA_alpha" in line and "ProjectAlpha" in line for line in captured)
    assert any("modelC_alpha" in line and "ProjectAlpha" in line for line in captured)

    # Check that other project entries are NOT present
    assert not any("modelB_beta" in line and "ProjectBeta" in line for line in captured)
    assert not any("model_no_project" in line and ",," in line for line in captured)

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_filter_by_project_null(mock_get_accounting, capsys, sqlite_backend_with_project_data):
    """Test `select --project NULL` filters for entries with no project."""
    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)

    with patch.object(sys, 'argv', ['cli_main', "select", "--project", "NULL", "--format", "csv"]):
        cli_main()
        
    captured = capsys.readouterr().out.strip().splitlines()

    # Expected CSV header
    header = captured[0].split(',')
    assert "id" in header
    assert "model" in header
    assert "project" in header

    # Check for the entry with project=NULL (which is an empty string in CSV)
    assert any("model_no_project" in line and ",0.4," in line and ",," in line for line in captured)

    # Check that other project entries are NOT present
    assert not any("modelA_alpha" in line and "ProjectAlpha" in line for line in captured)
    assert not any("modelB_beta" in line and "ProjectBeta" in line for line in captured)
    assert not any("modelC_alpha" in line and "ProjectAlpha" in line for line in captured)

@pytest.fixture
def sqlite_backend_with_project_data(sqlite_backend):
    """Pre-fill SQLite backend with data including different project values."""
    backend = sqlite_backend
    backend.insert_usage(UsageEntry(model="modelA_alpha", cost=0.1, execution_time=1, project="ProjectAlpha"))
    backend.insert_usage(UsageEntry(model="modelB_beta", cost=0.2, execution_time=1, project="ProjectBeta"))
    backend.insert_usage(UsageEntry(model="modelC_alpha", cost=0.3, execution_time=1, project="ProjectAlpha"))
    backend.insert_usage(UsageEntry(model="model_no_project", cost=0.4, execution_time=1, project=None))
    return backend
