import sys
from unittest.mock import patch
from llm_accounting.cli.main import main as cli_main
from llm_accounting import LLMAccounting, SQLiteBackend


def run_cli(db_path, args_list):
    with patch.object(sys, 'argv', ['cli_main'] + args_list):
        cli_main()


def test_cli_user_management(tmp_path, capsys):
    db_path = str(tmp_path / 'users.sqlite')
    backend = SQLiteBackend(db_path=db_path)
    acc = LLMAccounting(backend=backend)
    with patch('llm_accounting.cli.utils.get_accounting', return_value=acc):
        run_cli(db_path, ['users', 'add', 'alice', '--ou-name', 'IT', '--email', 'a@example.com'])
        captured = capsys.readouterr().out
        assert "User 'alice' added." in captured

        run_cli(db_path, ['users', 'list'])
        captured = capsys.readouterr().out
        assert 'alice' in captured

        run_cli(db_path, ['users', 'update', 'alice', 'alice2'])
        captured = capsys.readouterr().out
        assert "renamed to 'alice2'" in captured

        run_cli(db_path, ['users', 'deactivate', 'alice2'])
        captured = capsys.readouterr().out
        assert "User 'alice2' deactivated." in captured

        run_cli(db_path, ['users', 'list'])
        captured = capsys.readouterr().out
        assert 'inactive' in captured
