import io
import contextlib
import pytest
from importlib.metadata import version
from llm_accounting.cli.main import main

def test_cli_version(monkeypatch):
    expected_version = version('llm-accounting')
    
    # Monkeypatch sys.argv and capture exit/output
    with monkeypatch.context() as m:
        m.setattr('sys.argv', ['llm-accounting', '--version'])
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
    assert exc_info.value.code == 0
    output = f.getvalue().strip()
    assert output == f'llm-accounting {expected_version}'
