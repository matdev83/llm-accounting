from llm_accounting import LLMAccounting, SQLiteBackend
import pytest


def test_user_enforcement(tmp_path):
    db_path = str(tmp_path / 'enf.sqlite')
    backend = SQLiteBackend(db_path=db_path)
    acc = LLMAccounting(backend=backend, enforce_user_names=True)
    acc.quota_service.create_user('alice')
    with acc:
        acc.quota_service.refresh_users_cache()
        acc.track_usage(model='gpt', cost=0.1, prompt_tokens=1, username='alice')
        with pytest.raises(ValueError):
            acc.track_usage(model='gpt', cost=0.1, prompt_tokens=1, username='bob')
