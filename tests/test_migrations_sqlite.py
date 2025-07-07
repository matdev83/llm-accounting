import os
import pathlib
import pytest
import logging
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from src.llm_accounting.models.base import Base
from src.llm_accounting.db_migrations import run_migrations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REVISION_INITIAL_TABLES = "82f27c891782"
REVISION_ADD_NOTES_COLUMN = "ba9718840e75"
# REVISION_ADD_INDICES = "aa1b2c3d4e5f" # Not directly used in these specific tests but good to keep track
REVISION_ADD_SESSION_AND_REJECTIONS = "e5f6c7a8d9b0" # Head revision

@pytest.fixture(scope="function")
def sqlite_db_url(tmp_path):
    db_file = tmp_path / "test_accounting_sqlite_migrations.sqlite"
    db_url = f"sqlite:///{db_file}"
    if db_file.exists():
        db_file.unlink()
    yield db_url

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
def alembic_config_sqlite(sqlite_db_url):
    if not pathlib.Path("alembic.ini").exists():
        pytest.skip("alembic.ini not found, skipping Alembic direct command tests.")
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sqlite_db_url)
    return cfg

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

def test_sqlite_initial_migration_creates_schema(sqlite_db_url, set_db_url_env, alembic_config_sqlite):
    logger.info(f"Running SQLite initial migration test with DB URL: {sqlite_db_url}")
    set_db_url_env(sqlite_db_url)
    run_migrations(db_url=sqlite_db_url)
    engine = create_engine(sqlite_db_url)

    expected_tables = set(Base.metadata.tables.keys())
    current_tables = set(get_table_names(engine))
    logger.info(f"Expected tables (SQLite): {expected_tables}")
    logger.info(f"Current tables in DB (SQLite): {current_tables}")

    assert expected_tables.issubset(current_tables), \
        f"Not all expected tables found in SQLite. Missing: {expected_tables - current_tables}"
    assert "alembic_version" in current_tables, "alembic_version table not found in SQLite."
    assert get_alembic_revision(engine) == REVISION_ADD_SESSION_AND_REJECTIONS, \
        f"Alembic version in SQLite should be at {REVISION_ADD_SESSION_AND_REJECTIONS} after initial run_migrations."

def test_sqlite_applies_new_migration_and_preserves_data(sqlite_db_url, set_db_url_env, alembic_config_sqlite):
    logger.info(f"Running SQLite data preservation test with DB URL: {sqlite_db_url}")
    set_db_url_env(sqlite_db_url)
    engine = create_engine(sqlite_db_url)

    logger.info(f"Upgrading SQLite to initial tables revision: {REVISION_INITIAL_TABLES}")
    alembic_command.upgrade(alembic_config_sqlite, REVISION_INITIAL_TABLES)
    current_revision = get_alembic_revision(engine)
    logger.info(f"Revision after initial SQLite upgrade: {current_revision}")
    assert current_revision == REVISION_INITIAL_TABLES

    accounting_columns_before = get_column_names(engine, "accounting_entries")
    logger.info(f"Columns in accounting_entries before 'add_notes' (SQLite): {accounting_columns_before}")
    assert "notes" not in accounting_columns_before

    logger.info("Adding dummy data to SQLite accounting_entries.")
    with engine.connect() as connection:
        stmt = text(
            "INSERT INTO accounting_entries (timestamp, model, cost, execution_time, cached_tokens, reasoning_tokens) "
            "VALUES (:ts, :model, :cost, :exec_time, :cached, :reasoning)"
        )
        connection.execute(
            stmt,
            {"ts": "2023-01-01T12:00:00", "model": "sqlite-test-model-1", "cost": 1.23, "exec_time": 0.5, "cached": 0, "reasoning": 0}
        )
        connection.commit()

    with engine.connect() as connection:
        result = connection.execute(text("SELECT COUNT(*) FROM accounting_entries")).scalar_one()
    assert result == 1, "Dummy data not inserted correctly in SQLite."
    logger.info("Dummy data inserted in SQLite.")

    logger.info("Running migrations again on SQLite to apply remaining migrations.")
    run_migrations(db_url=sqlite_db_url)

    current_revision_after_second_run = get_alembic_revision(engine)
    logger.info(f"Revision after second run_migrations (SQLite): {current_revision_after_second_run}")
    assert current_revision_after_second_run == REVISION_ADD_SESSION_AND_REJECTIONS

    accounting_columns_after = get_column_names(engine, "accounting_entries")
    logger.info(f"Columns in accounting_entries after 'add_notes' (SQLite): {accounting_columns_after}")
    assert "notes" in accounting_columns_after, "'notes' column not found in SQLite after migration."

    logger.info("Verifying data preservation in SQLite.")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT model, cost, execution_time FROM accounting_entries WHERE model = 'sqlite-test-model-1'")
        ).first()

    assert row is not None, "Previously inserted row not found in SQLite."
    assert row._mapping["model"] == "sqlite-test-model-1"
    assert row._mapping["cost"] == 1.23
    assert abs(row._mapping["execution_time"] - 0.5) < 1e-9
    logger.info("Data preservation verified in SQLite.")
