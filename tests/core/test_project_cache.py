from llm_accounting import LLMAccounting, SQLiteBackend


def test_project_cache_refresh(tmp_path):
    db = str(tmp_path / 'cache.sqlite')
    backend = SQLiteBackend(db_path=db)
    acc = LLMAccounting(backend=backend)
    with acc:
        acc.quota_service.create_project('One')
        projects = acc.quota_service.list_projects()
        assert projects == ['One']
        acc.quota_service.create_project('Two')
        projects2 = acc.quota_service.list_projects()
        assert set(projects2) == {'One', 'Two'}
