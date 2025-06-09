import sys
from unittest.mock import patch
from llm_accounting.cli.main import main as cli_main
from llm_accounting import LLMAccounting, SQLiteBackend


def run_cli(db_path, args_list):
    with patch.object(sys, 'argv', ['cli_main'] + args_list):
        cli_main()


def test_cli_project_management(tmp_path, capsys):
    db_path = str(tmp_path / 'proj.sqlite')
    backend = SQLiteBackend(db_path=db_path)
    acc = LLMAccounting(backend=backend)
    with patch('llm_accounting.cli.utils.get_accounting', return_value=acc):
        run_cli(db_path, ['projects', 'add', 'Alpha'])
        captured = capsys.readouterr().out
        assert "Project 'Alpha' added." in captured

        run_cli(db_path, ['projects', 'list'])
        captured = capsys.readouterr().out
        assert 'Alpha' in captured

        run_cli(db_path, ['projects', 'update', 'Alpha', 'Beta'])
        captured = capsys.readouterr().out
        assert "renamed to 'Beta'" in captured

        run_cli(db_path, ['projects', 'delete', 'Beta'])
        captured = capsys.readouterr().out
        assert "Project 'Beta' deleted." in captured

        run_cli(db_path, ['projects', 'list'])
        captured = capsys.readouterr().out
        assert 'No projects' in captured
