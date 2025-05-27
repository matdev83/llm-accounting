import sys
import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime
from llm_accounting import LLMAccounting
from llm_accounting.cli.main import main as cli_main
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from llm_accounting.backends.sqlite import SQLiteBackend # Using real backend

@pytest.fixture
def fresh_sqlite_backend_for_cli(tmp_path):
    """Provides a completely fresh SQLiteBackend instance for each CLI test."""
    db_path = tmp_path / f"test_cli_limits_project_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.sqlite"
    backend = SQLiteBackend(db_path=str(db_path))
    # LLMAccounting context manager will call backend.initialize()
    return backend

@pytest.fixture
def accounting_for_cli(fresh_sqlite_backend_for_cli):
    """Provides an LLMAccounting instance with a fresh SQLite backend for CLI tests."""
    # The CLI main function creates its own LLMAccounting instance.
    # This fixture is more for direct backend manipulation if needed, or to guide mock_get_accounting.
    # We will primarily rely on mocking get_accounting to inject our backend.
    return LLMAccounting(backend=fresh_sqlite_backend_for_cli)


@patch("llm_accounting.cli.utils.get_accounting")
def test_cli_limits_set_project_scope_success(mock_get_accounting, fresh_sqlite_backend_for_cli, capsys):
    """Test `llmacct limits set --scope PROJECT --project-name <name> ...` succeeds."""
    mock_get_accounting.return_value = LLMAccounting(backend=fresh_sqlite_backend_for_cli)
    
    project_name = "CLIProjectAlpha"
    args = [
        'cli_main', "limits", "set",
        "--scope", "PROJECT",
        "--limit-type", "cost",
        "--max-value", "100.50",
        "--interval-unit", "monthly",
        "--interval-value", "1",
        "--project-name", project_name
    ]
    with patch.object(sys, 'argv', args):
        cli_main()
    
    captured = capsys.readouterr()
    assert "Usage limit set successfully." in captured.out

    # Verify in backend
    limits = fresh_sqlite_backend_for_cli.get_usage_limits(scope=LimitScope.PROJECT, project_name=project_name)
    assert len(limits) == 1
    limit = limits[0]
    assert limit.scope == LimitScope.PROJECT.value
    assert limit.project_name == project_name
    assert limit.limit_type == LimitType.COST.value
    assert limit.max_value == 100.50
    assert limit.interval_unit == TimeInterval.MONTH.value # 'monthly' from CLI
    assert limit.interval_value == 1

@patch("llm_accounting.cli.utils.get_accounting")
def test_cli_limits_set_project_scope_missing_project_name(mock_get_accounting, fresh_sqlite_backend_for_cli, capsys):
    """Test `llmacct limits set --scope PROJECT` fails without --project-name."""
    mock_get_accounting.return_value = LLMAccounting(backend=fresh_sqlite_backend_for_cli)

    args = [
        'cli_main', "limits", "set",
        "--scope", "PROJECT",
        "--limit-type", "cost",
        "--max-value", "100.0",
        "--interval-unit", "day",
        "--interval-value", "1"
        # Missing --project-name
    ]
    with patch.object(sys, 'argv', args):
        cli_main() # Should print error and not raise SystemExit based on current limits.py
    
    captured = capsys.readouterr()
    assert "Error: --project-name is required when scope is PROJECT." in captured.out
    
    # Verify no limit was created
    limits = fresh_sqlite_backend_for_cli.get_usage_limits(scope=LimitScope.PROJECT)
    assert len(limits) == 0


@patch("llm_accounting.cli.utils.get_accounting")
def test_cli_limits_list_with_project_filters(mock_get_accounting, fresh_sqlite_backend_for_cli, capsys):
    """Test `llmacct limits list` with project-related filters."""
    acc_instance = LLMAccounting(backend=fresh_sqlite_backend_for_cli)
    mock_get_accounting.return_value = acc_instance

    # Setup: Create some limits
    acc_instance.set_usage_limit(LimitScope.GLOBAL, LimitType.COST, 1000, TimeInterval.MONTH, 1)
    acc_instance.set_usage_limit(LimitScope.PROJECT, LimitType.REQUESTS, 100, TimeInterval.DAY, 1, project_name="WebApp")
    acc_instance.set_usage_limit(LimitScope.PROJECT, LimitType.COST, 50, TimeInterval.DAY, 1, project_name="MobileApp")
    acc_instance.set_usage_limit(LimitScope.PROJECT, LimitType.COST, 75, TimeInterval.WEEK, 1, project_name="WebApp", model="gpt-4")


    # 1. List all (should show all, including project details)
    with patch.object(sys, 'argv', ['cli_main', "limits", "list"]):
        cli_main()
    captured_all = capsys.readouterr().out
    assert "GLOBAL" in captured_all
    assert "Project: WebApp" in captured_all
    assert "Project: MobileApp" in captured_all
    assert "Model: gpt-4" in captured_all # For the WebApp gpt-4 limit
    assert "ID:" in captured_all # Basic check it's listing limits

    # 2. List --scope PROJECT
    with patch.object(sys, 'argv', ['cli_main', "limits", "list", "--scope", "PROJECT"]):
        cli_main()
    captured_project_scope = capsys.readouterr().out
    assert "GLOBAL" not in captured_project_scope
    assert "Project: WebApp" in captured_project_scope
    assert "Project: MobileApp" in captured_project_scope
    assert len(captured_project_scope.split("ID:")) -1 == 3 # Should be 3 project limits

    # 3. List --project-name WebApp
    with patch.object(sys, 'argv', ['cli_main', "limits", "list", "--project-name", "WebApp"]):
        cli_main()
    captured_project_webapp = capsys.readouterr().out
    assert "Project: WebApp" in captured_project_webapp
    assert "MobileApp" not in captured_project_webapp
    assert len(captured_project_webapp.split("ID:")) - 1 == 2 # Two limits for WebApp

    # 4. List --scope PROJECT --project-name MobileApp
    with patch.object(sys, 'argv', ['cli_main', "limits", "list", "--scope", "PROJECT", "--project-name", "MobileApp"]):
        cli_main()
    captured_project_mobileapp = capsys.readouterr().out
    assert "Project: MobileApp" in captured_project_mobileapp
    assert "WebApp" not in captured_project_mobileapp
    assert len(captured_project_mobileapp.split("ID:")) - 1 == 1


@patch("llm_accounting.cli.utils.get_accounting")
def test_cli_limits_delete_project_limit(mock_get_accounting, fresh_sqlite_backend_for_cli, capsys):
    """Test deleting a project-specific limit via CLI."""
    acc_instance = LLMAccounting(backend=fresh_sqlite_backend_for_cli)
    mock_get_accounting.return_value = acc_instance

    project_name = "ToDeleteProject"
    acc_instance.set_usage_limit(
        scope=LimitScope.PROJECT, limit_type=LimitType.COST, max_value=10.0,
        interval_unit=TimeInterval.DAY, interval_value=1, project_name=project_name
    )
    limits_before_delete = acc_instance.get_usage_limits(project_name=project_name)
    assert len(limits_before_delete) == 1
    limit_id_to_delete = limits_before_delete[0].id
    assert limit_id_to_delete is not None

    # Delete the limit
    with patch.object(sys, 'argv', ['cli_main', "limits", "delete", "--id", str(limit_id_to_delete)]):
        cli_main()
    captured = capsys.readouterr()
    assert f"Usage limit with ID {limit_id_to_delete} deleted successfully." in captured.out

    # Verify it's deleted
    limits_after_delete = acc_instance.get_usage_limits(project_name=project_name)
    assert len(limits_after_delete) == 0
