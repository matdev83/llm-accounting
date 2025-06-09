from llm_accounting import LLMAccounting, SQLiteBackend
import pytest


def test_project_enforcement(tmp_path):
    db_path = str(tmp_path / 'enf.sqlite')
    backend = SQLiteBackend(db_path=db_path)
    acc = LLMAccounting(backend=backend, enforce_project_names=True)
    acc.quota_service.create_project('Allowed')
    with acc:
        acc.quota_service.refresh_projects_cache()
        # allowed project
        acc.track_usage(model='gpt', cost=0.1, prompt_tokens=1, project='Allowed')
        # invalid project
        with pytest.raises(ValueError):
            acc.track_usage(model='gpt', cost=0.1, prompt_tokens=1, project='Bad')
