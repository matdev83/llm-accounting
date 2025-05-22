import pytest
import subprocess
import sys
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval
from llm_accounting import LLMAccounting, SQLiteBackend
import os

@pytest.fixture
def temp_db_file(tmp_path):
    db_path = tmp_path / "test_accounting.sqlite"
    yield str(db_path)
    if os.path.exists(db_path):
        os.remove(db_path)

def run_cli_command(db_file, command_args):
    """Helper to run CLI commands using subprocess."""
    cmd = [sys.executable, "-m", "llm_accounting.cli.main", "--db-file", db_file] + command_args
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    print(f"\n--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}")
    return result

def test_add_limit_global_requests(temp_db_file):
    result = run_cli_command(
        temp_db_file,
        [
            "limits",
            "add",
            "--scope",
            "global",
            "--limit-type",
            "requests",
            "--max-value",
            "100",
            "--interval-unit",
            "hour",
            "--interval-value",
            "1",
        ],
    )
    assert result.returncode == 0, result.stderr
    assert "Usage limit added successfully" in result.stdout

    # Verify the limit was added to the database
    accounting = LLMAccounting(backend=SQLiteBackend(db_path=temp_db_file))
    with accounting:
        limits = accounting.get_limits()
        assert len(limits) == 1
        limit = limits[0]
        assert limit.scope == LimitScope.GLOBAL.value
        assert limit.limit_type == LimitType.REQUESTS.value
        assert limit.max_value == 100.0
        assert limit.interval_unit == TimeInterval.HOUR.value
        assert limit.interval_value == 1

def test_add_limit_model_cost(temp_db_file):
    result = run_cli_command(
        temp_db_file,
        [
            "limits",
            "add",
            "--scope",
            "model",
            "--limit-type",
            "cost",
            "--max-value",
            "50.5",
            "--interval-unit",
            "day",
            "--interval-value",
            "7",
            "--model",
            "gpt-4",
        ],
    )
    assert result.returncode == 0, result.stderr
    assert "Usage limit added successfully" in result.stdout

    # Verify the limit was added to the database
    accounting = LLMAccounting(backend=SQLiteBackend(db_path=temp_db_file))
    with accounting:
        limits = accounting.get_limits()
        assert len(limits) == 1
        limit = limits[0]
        assert limit.scope == LimitScope.MODEL.value
        assert limit.limit_type == LimitType.COST.value
        assert limit.max_value == 50.5
        assert limit.interval_unit == TimeInterval.DAY.value
        assert limit.interval_value == 7
        assert limit.model == "gpt-4"

def test_add_limit_user_input_tokens(temp_db_file):
    result = run_cli_command(
        temp_db_file,
        [
            "limits",
            "add",
            "--scope",
            "user",
            "--limit-type",
            "input_tokens",
            "--max-value",
            "100000",
            "--interval-unit",
            "month",
            "--interval-value",
            "1",
            "--username",
            "test_user",
        ],
    )
    assert result.returncode == 0, result.stderr
    assert "Usage limit added successfully" in result.stdout

    # Verify the limit was added to the database
    accounting = LLMAccounting(backend=SQLiteBackend(db_path=temp_db_file))
    with accounting:
        limits = accounting.get_limits()
        assert len(limits) == 1
        limit = limits[0]
        assert limit.scope == LimitScope.USER.value
        assert limit.limit_type == LimitType.INPUT_TOKENS.value
        assert limit.max_value == 100000.0
        assert limit.interval_unit == TimeInterval.MONTH.value
        assert limit.interval_value == 1
        assert limit.username == "test_user"

def test_add_limit_invalid_scope(temp_db_file):
    result = run_cli_command(
        temp_db_file,
        [
            "limits",
            "add",
            "--scope",
            "invalid_scope",
            "--limit-type",
            "requests",
            "--max-value",
            "100",
            "--interval-unit",
            "hour",
            "--interval-value",
            "1",
        ],
    )
    assert result.returncode == 2
    assert "argument --scope: invalid choice: 'invalid_scope'" in result.stderr

def test_add_limit_missing_required_args(temp_db_file):
    result = run_cli_command(
        temp_db_file,
        [
            "limits",
            "add",
            "--scope",
            "global",
            "--limit-type",
            "requests",
            "--interval-unit",
            "hour",
            "--interval-value",
            "1",
        ],
    )
    assert result.returncode == 2 # argparse error for missing required argument
    assert "the following arguments are required: --max-value" in result.stderr


def test_view_limits(temp_db_file):
    # Add a few limits first
    run_cli_command(
        temp_db_file,
        [
            "limits", "add",
            "--scope", "global", "--limit-type", "requests", "--max-value", "100",
            "--interval-unit", "hour", "--interval-value", "1",
        ],
    )
    run_cli_command(
        temp_db_file,
        [
            "limits", "add",
            "--scope", "model", "--limit-type", "cost", "--max-value", "50.5",
            "--interval-unit", "day", "--interval-value", "7", "--model", "gpt-4",
        ],
    )

    result = run_cli_command(temp_db_file, ["limits", "view"])
    assert result.returncode == 0, result.stderr
    assert "Existing Usage Limits" in result.stdout # type: ignore
    assert "global" in result.stdout # type: ignore
    assert "requests" in result.stdout # type: ignore
    assert "100.0" in result.stdout # type: ignore
    assert "1 hour" in result.stdout # type: ignore
    assert "model" in result.stdout # type: ignore
    assert "cost" in result.stdout # type: ignore
    assert "50.5" in result.stdout # type: ignore
    assert "7 day" in result.stdout # type: ignore
    assert "gpt-4" in result.stdout # type: ignore


def test_delete_limit(temp_db_file):
    # Add a limit to delete
    add_result = run_cli_command(
        temp_db_file,
        [
            "limits", "add",
            "--scope", "global", "--limit-type", "requests", "--max-value", "100",
            "--interval-unit", "hour", "--interval-value", "1",
        ],
    )
    assert add_result.returncode == 0

    # Get the ID of the added limit
    accounting = LLMAccounting(backend=SQLiteBackend(db_path=temp_db_file))
    with accounting:
        limits = accounting.get_limits()
        assert len(limits) == 1
        limit_id = limits[0].id

    # Delete the limit
    delete_result = run_cli_command(temp_db_file, ["limits", "delete", "--id", str(limit_id)])
    assert delete_result.returncode == 0, delete_result.stderr
    assert f"Usage limit with ID {limit_id} deleted successfully" in delete_result.stdout

    # Verify the limit is gone
    with accounting:
        limits_after_delete = accounting.get_limits()
        assert len(limits_after_delete) == 0

def test_delete_non_existent_limit(temp_db_file):
    result = run_cli_command(temp_db_file, ["limits", "delete", "--id", "999"])
    assert result.returncode == 1
    assert "Error deleting limit: No such limit with ID 999" in result.stdout
