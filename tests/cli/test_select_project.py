import sys
import pytest
from unittest.mock import patch, MagicMock
from llm_accounting import LLMAccounting, UsageEntry
from llm_accounting.cli.main import main as cli_main
import io
from rich.console import Console
from argparse import Namespace

from llm_accounting.cli.commands.select import _construct_query


def make_cli_test_entry(**kwargs):
    entry = MagicMock(spec=UsageEntry)
    entry.model = kwargs.get("model", "gpt-4")
    entry.prompt_tokens = kwargs.get("prompt_tokens", 0)
    entry.completion_tokens = kwargs.get("completion_tokens", 0)
    entry.total_tokens = kwargs.get("total_tokens", 0)
    entry.cost = kwargs.get("cost", 0.0)
    entry.execution_time = kwargs.get("execution_time", 0.0)
    entry.timestamp = kwargs.get("timestamp", MagicMock())
    entry.timestamp.strftime.return_value = "2024-01-01 12:00:00"
    entry.caller_name = kwargs.get("caller_name", "")
    entry.username = kwargs.get("username", "")
    entry.project = kwargs.get("project", None)
    entry.cached_tokens = kwargs.get("cached_tokens", 0)
    entry.reasoning_tokens = kwargs.get("reasoning_tokens", 0)
    
    dict_representation = {
        'id': kwargs.get('id', 1),
        'timestamp': entry.timestamp.strftime.return_value,
        'model': entry.model,
        'prompt_tokens': entry.prompt_tokens,
        'completion_tokens': entry.completion_tokens,
        'total_tokens': entry.total_tokens,
        'local_prompt_tokens': kwargs.get('local_prompt_tokens', 0),
        'local_completion_tokens': kwargs.get('local_completion_tokens', 0),
        'local_total_tokens': kwargs.get('local_total_tokens', 0),
        'project': entry.project if entry.project is not None else "",
        'cost': entry.cost,
        'execution_time': entry.execution_time,
        'caller_name': entry.caller_name,
        'username': entry.username,
        'cached_tokens': entry.cached_tokens,
        'reasoning_tokens': entry.reasoning_tokens,
    }
    entry.configure_mock(**dict_representation)

    def getitem_side_effect(key):
        return dict_representation[key]
    entry.__getitem__.side_effect = getitem_side_effect
    entry.keys.return_value = dict_representation.keys()
    entry.values.return_value = dict_representation.values()
    
    return entry

def test_debug_construct_query_no_project_filter():
    print("\n--- test_debug_construct_query_no_project_filter ---")
    args = Namespace(
        query=None,
        project=None,
        format="csv",
        command='select'
    )
    print(f"Mock Args: {args!r}")
    query_to_execute = ""
    try:
        query_to_execute = _construct_query(args)
        print(f"Query constructed: '{query_to_execute}'")
    except Exception as e:
        print(f"Exception in _construct_query: {e!r}")
    assert query_to_execute == "SELECT * FROM accounting_entries;", "Query construction failed for no_project_filter"
    print("--- End test_debug_construct_query_no_project_filter ---")


@patch("llm_accounting.cli.utils.get_accounting")
def test_select_no_project_filter_displays_project_column(mock_get_accounting, sqlite_backend_with_project_data):
    string_io = io.StringIO()
    test_console = Console(file=string_io) # Removed force_terminal=False

    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)

    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--format", "csv"]):
            cli_main()
    
    captured_output = string_io.getvalue()
    captured_out_lines = captured_output.strip().splitlines()

    # --- Debugging Print ---
    # print("\nCaptured stdout for test_select_no_project_filter_displays_project_column:")
    # for line_idx, line in enumerate(captured_out_lines):
    #     print(f"Line {line_idx}: {line}")
    # print("--- End captured stdout ---")
    # --- End Debugging Print ---

    assert captured_out_lines, f"stdout should not be empty. Captured output: '{captured_output}'"
    # Remove debug lines before header processing
    debug_line_prefix = "--- DEBUG:"
    csv_lines = [line for line in captured_out_lines if not line.startswith(debug_line_prefix)]
    assert csv_lines, f"CSV output should not be empty after filtering debug lines. Original captured: {captured_output}"

    header = csv_lines[0].split(',')
    assert "id" in header
    assert "model" in header
    assert "project" in header
    assert "cost" in header
    
    assert any("modelA_alpha" in line and "ProjectAlpha" in line for line in csv_lines)
    assert any("modelB_beta" in line and "ProjectBeta" in line for line in csv_lines)
    assert any("modelC_alpha" in line and "ProjectAlpha" in line for line in csv_lines)
    assert any("model_no_project" in line and ",0.4," in line and ",," in line for line in csv_lines)

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_filter_by_project_name(mock_get_accounting, sqlite_backend_with_project_data):
    string_io = io.StringIO()
    test_console = Console(file=string_io) # Removed force_terminal=False

    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)
    project_to_filter = "ProjectAlpha"

    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--project", project_to_filter, "--format", "csv"]):
            cli_main()
        
    captured_output = string_io.getvalue()
    captured_out_lines = captured_output.strip().splitlines()

    # print(f"\nCaptured stdout for test_select_filter_by_project_name (filter: {project_to_filter}):")
    # for line_idx, line in enumerate(captured_out_lines):
    #     print(f"Line {line_idx}: {line}")
    # print("--- End captured stdout ---")

    assert captured_out_lines, f"stdout should not be empty. Captured output: '{captured_output}'"
    debug_line_prefix = "--- DEBUG:"
    csv_lines = [line for line in captured_out_lines if not line.startswith(debug_line_prefix)]
    assert csv_lines, f"CSV output should not be empty after filtering debug lines. Original captured: {captured_output}"

    header = csv_lines[0].split(',')
    assert "id" in header
    assert "model" in header
    assert "project" in header

    assert any("modelA_alpha" in line and "ProjectAlpha" in line for line in csv_lines)
    assert any("modelC_alpha" in line and "ProjectAlpha" in line for line in csv_lines)

    assert not any("modelB_beta" in line and "ProjectBeta" in line for line in csv_lines)
    assert not any("model_no_project" in line and ",," in line for line in csv_lines)

@patch("llm_accounting.cli.utils.get_accounting")
def test_select_filter_by_project_null(mock_get_accounting, sqlite_backend_with_project_data):
    string_io = io.StringIO()
    test_console = Console(file=string_io) # Removed force_terminal=False

    mock_get_accounting.return_value = LLMAccounting(backend=sqlite_backend_with_project_data)

    with patch('llm_accounting.cli.commands.select.console', test_console):
        with patch.object(sys, 'argv', ['cli_main', "select", "--project", "NULL", "--format", "csv"]):
            cli_main()
        
    captured_output = string_io.getvalue()
    captured_out_lines = captured_output.strip().splitlines()

    # print(f"\nCaptured stdout for test_select_filter_by_project_null (filter: NULL):")
    # for line_idx, line in enumerate(captured_out_lines):
    #     print(f"Line {line_idx}: {line}")
    # print("--- End captured stdout ---")

    assert captured_out_lines, f"stdout should not be empty. Captured output: '{captured_output}'"
    debug_line_prefix = "--- DEBUG:"
    csv_lines = [line for line in captured_out_lines if not line.startswith(debug_line_prefix)]
    assert csv_lines, f"CSV output should not be empty after filtering debug lines. Original captured: {captured_output}"

    header = csv_lines[0].split(',')
    assert "id" in header
    assert "model" in header
    assert "project" in header

    assert any("model_no_project" in line and ",0.4," in line and ",," in line for line in csv_lines)

    assert not any("modelA_alpha" in line and "ProjectAlpha" in line for line in csv_lines)
    assert not any("modelB_beta" in line and "ProjectBeta" in line for line in csv_lines)
    assert not any("modelC_alpha" in line and "ProjectAlpha" in line for line in csv_lines)

@pytest.fixture
def sqlite_backend_with_project_data(sqlite_backend):
    backend = sqlite_backend
    backend.initialize()

    backend.insert_usage(UsageEntry(model="modelA_alpha", cost=0.1, execution_time=1.0, project="ProjectAlpha", prompt_tokens=1, completion_tokens=1, total_tokens=2))
    backend.insert_usage(UsageEntry(model="modelB_beta", cost=0.2, execution_time=1.0, project="ProjectBeta", prompt_tokens=1, completion_tokens=1, total_tokens=2))
    backend.insert_usage(UsageEntry(model="modelC_alpha", cost=0.3, execution_time=1.0, project="ProjectAlpha", prompt_tokens=1, completion_tokens=1, total_tokens=2))
    backend.insert_usage(UsageEntry(model="model_no_project", cost=0.4, execution_time=1.0, project=None, prompt_tokens=1, completion_tokens=1, total_tokens=2))
    return backend
