import sys
from unittest.mock import patch
from llm_accounting.cli.main import main as cli_main
from llm_accounting import LLMAccounting, SQLiteBackend


def run_cli(args_list):
    with patch.object(sys, 'argv', ['cli_main'] + args_list):
        cli_main()


def test_cli_user_management(tmp_path, capsys):
    db_path = str(tmp_path / 'u.sqlite')
    backend = SQLiteBackend(db_path=db_path)
    acc = LLMAccounting(backend=backend)
    with patch('llm_accounting.cli.utils.get_accounting', return_value=acc):
        run_cli(['users', 'add', 'alice'])
        captured = capsys.readouterr().out
        assert "User 'alice' added." in captured

        run_cli(['users', 'list'])
        captured = capsys.readouterr().out
        assert 'alice' in captured

        run_cli(['users', 'update', 'alice', '--new-user-name', 'bob'])
        captured = capsys.readouterr().out
        assert 'updated' in captured

        run_cli(['users', 'deactivate', 'bob'])
        captured = capsys.readouterr().out
        assert 'deactivated' in captured

        run_cli(['users', 'list'])
        captured = capsys.readouterr().out
        assert 'bob' in captured
