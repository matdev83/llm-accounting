from llm_accounting import LLMAccounting, SQLiteBackend


def test_user_cache_refresh(tmp_path):
    db = str(tmp_path / 'cache.sqlite')
    backend = SQLiteBackend(db_path=db)
    acc = LLMAccounting(backend=backend)
    with acc:
        acc.quota_service.create_user('alice')
        users = acc.quota_service.list_users()
        assert users == ['alice']
        acc.quota_service.create_user('bob')
        users2 = acc.quota_service.list_users()
        assert set(users2) == {'alice', 'bob'}
