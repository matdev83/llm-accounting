import pytest
from llm_accounting import LLMAccounting, SQLiteBackend


def test_user_enforcement(tmp_path):
    db_path = str(tmp_path / 'enf.sqlite')
    backend = SQLiteBackend(db_path=db_path)
    acc = LLMAccounting(backend=backend, enforce_user_names=True)
    acc.quota_service.create_user('john')
    with acc:
        acc.quota_service.refresh_users_cache()
        acc.track_usage(model='gpt', cost=0.1, prompt_tokens=1, username='john')
        with pytest.raises(ValueError):
            acc.track_usage(model='gpt', cost=0.1, prompt_tokens=1, username='bad')
