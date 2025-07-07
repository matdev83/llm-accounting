import os
import pathlib
import pytest
import logging
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from src.llm_accounting.models.base import Base
from src.llm_accounting.db_migrations import run_migrations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REVISION_INITIAL_TABLES = "82f27c891782"
REVISION_ADD_NOTES_COLUMN = "ba9718840e75"
# REVISION_ADD_INDICES = "aa1b2c3d4e5f" # Not directly used
REVISION_ADD_SESSION_AND_REJECTIONS = "e5f6c7a8d9b0" # Head revision

TEST_POSTGRESQL_URL = os.environ.get("TEST_POSTGRESQL_DB_URL")

@pytest.fixture(scope="function")
def set_db_url_env(monkeypatch):
    original_url = os.environ.get("LLM_ACCOUNTING_DB_URL")
    def _set_url(url):
        monkeypatch.setenv("LLM_ACCOUNTING_DB_URL", url)
    yield _set_url
    if original_url is None:
        monkeypatch.delenv("LLM_ACCOUNTING_DB_URL", raising=False)
    else:
        monkeypatch.setenv("LLM_ACCOUNTING_DB_URL", original_url)

@pytest.fixture(scope="function")
def alembic_config_postgresql():
    if not TEST_POSTGRESQL_URL:
        pytest.skip("TEST_POSTGRESQL_DB_URL not set, skipping PostgreSQL Alembic config.")
    if not pathlib.Path("alembic.ini").exists():
        pytest.skip("alembic.ini not found, skipping Alembic direct command tests.")
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_POSTGRESQL_URL)
    return cfg

@pytest.fixture(scope="function")
def postgresql_engine():
    if not TEST_POSTGRESQL_URL:
        pytest.skip("TEST_POSTGRESQL_DB_URL not set, skipping PostgreSQL engine fixture.")
    engine = create_engine(TEST_POSTGRESQL_URL)
    with engine.connect() as connection:
        try:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
            connection.commit()
        except Exception as e:
            logger.warning(f"Could not drop alembic_version table during PG cleanup: {e}")
        for table in reversed(Base.metadata.sorted_tables):
            try:
                table.drop(connection, checkfirst=True)
                logger.info(f"Dropped table {table.name} for PG test setup.")
            except Exception as e:
                logger.warning(f"Could not drop table {table.name} during PG cleanup: {e}")
        connection.commit()
    yield engine

def get_table_names(engine):
    inspector = inspect(engine)
    return inspector.get_table_names()

def get_column_names(engine, table_name):
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return [col['name'] for col in columns]

def get_alembic_revision(engine):
    with engine.connect() as connection:
        try:
            result = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            return result
        except Exception as e:
            logger.error(f"Could not query alembic_version table: {e}")
            return None

@pytest.mark.skipif(not TEST_POSTGRESQL_URL, reason="TEST_POSTGRESQL_DB_URL not set")
def test_postgresql_initial_migration_creates_schema(postgresql_engine, set_db_url_env, alembic_config_postgresql):
    logger.info(f"Running PostgreSQL initial migration test with DB URL: {TEST_POSTGRESQL_URL}")
    set_db_url_env(TEST_POSTGRESQL_URL)
    assert TEST_POSTGRESQL_URL is not None
    run_migrations(db_url=TEST_POSTGRESQL_URL)

    expected_tables = set(Base.metadata.tables.keys())
    current_tables = set(get_table_names(postgresql_engine))
    logger.info(f"Expected tables (PG): {expected_tables}")
    logger.info(f"Current tables in DB (PG): {current_tables}")

    assert expected_tables.issubset(current_tables), \
        f"Not all expected tables found in PG. Missing: {expected_tables - current_tables}"
    assert "alembic_version" in current_tables, "alembic_version table not found in PG."
    assert get_alembic_revision(postgresql_engine) == REVISION_ADD_SESSION_AND_REJECTIONS, \
        f"Alembic version in PG should be at {REVISION_ADD_SESSION_AND_REJECTIONS}."

@pytest.mark.skipif(not TEST_POSTGRESQL_URL, reason="TEST_POSTGRESQL_DB_URL not set")
def test_postgresql_applies_new_migration_and_preserves_data(postgresql_engine, set_db_url_env, alembic_config_postgresql):
    logger.info(f"Running PostgreSQL data preservation test with DB URL: {TEST_POSTGRESQL_URL}")
    set_db_url_env(TEST_POSTGRESQL_URL)
    assert TEST_POSTGRESQL_URL is not None

    logger.info(f"Upgrading PG to initial tables revision: {REVISION_INITIAL_TABLES}")
    alembic_command.upgrade(alembic_config_postgresql, REVISION_INITIAL_TABLES)
    assert get_alembic_revision(postgresql_engine) == REVISION_INITIAL_TABLES

    accounting_columns_before = get_column_names(postgresql_engine, "accounting_entries")
    assert "notes" not in accounting_columns_before

    logger.info("Adding dummy data to PG accounting_entries.")
    with postgresql_engine.connect() as connection:
        stmt = text(
            "INSERT INTO accounting_entries (timestamp, model, cost, execution_time, cached_tokens, reasoning_tokens) "
            "VALUES (:ts, :model, :cost, :exec_time, :cached, :reasoning)"
        )
        connection.execute(
            stmt,
            {"ts": datetime(2023, 1, 1, 12, 0, 0), "model": "pg-test-model-1", "cost": 4.56, "exec_time": 0.7, "cached": 0, "reasoning": 0}
        )
        connection.commit()

    with postgresql_engine.connect() as connection:
        result = connection.execute(text("SELECT COUNT(*) FROM accounting_entries")).scalar_one()
    assert result == 1, "Dummy data not inserted correctly in PG."
    logger.info("Dummy data inserted in PG.")

    logger.info("Running migrations again on PG to apply remaining migrations.")
    run_migrations(db_url=TEST_POSTGRESQL_URL)

    assert get_alembic_revision(postgresql_engine) == REVISION_ADD_SESSION_AND_REJECTIONS
    accounting_columns_after = get_column_names(postgresql_engine, "accounting_entries")
    assert "notes" in accounting_columns_after, "'notes' column not found in PG after migration."

    logger.info("Verifying data preservation in PG.")
    with postgresql_engine.connect() as connection:
        row = connection.execute(
            text("SELECT model, cost, execution_time FROM accounting_entries WHERE model = 'pg-test-model-1'")
        ).first()

    assert row is not None, "Previously inserted row not found in PG."
    assert row._mapping["model"] == "pg-test-model-1"
    assert row._mapping["cost"] == 4.56
    assert abs(row._mapping["execution_time"] - 0.7) < 1e-9
    logger.info("Data preservation verified in PG.")
