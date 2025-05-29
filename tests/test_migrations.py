import os
import pathlib
import pytest
import logging
from datetime import datetime # Added for PostgreSQL test fixture
from sqlalchemy import create_engine, inspect, text, Column, Integer, String, DateTime, Float # Added more types for dummy data
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

# Ensure all models are imported so Base.metadata is populated
from src.llm_accounting.models.base import Base
from src.llm_accounting.models.accounting import AccountingEntry
from src.llm_accounting.models.audit import AuditLogEntryModel
from src.llm_accounting.models.limits import UsageLimit

# Function to be tested
from src.llm_accounting.db_migrations import run_migrations

# Configure logging for tests (optional, but can be helpful)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Revision IDs (obtained from previous steps) ---
REVISION_INITIAL_TABLES = "82f27c891782"
REVISION_ADD_NOTES_COLUMN = "ba9718840e75"


# --- Fixtures ---

@pytest.fixture(scope="function")
def sqlite_db_url(tmp_path):
    """Provides a temporary SQLite database URL and ensures the db file is cleaned up."""
    db_file = tmp_path / "test_accounting.sqlite"
    db_url = f"sqlite:///{db_file}"
    
    # Ensure the db file does not exist at the start of a test
    if db_file.exists():
        db_file.unlink()
        
    yield db_url
    
    # Cleanup: ensure the db file is removed after the test
    # if db_file.exists():
    #     db_file.unlink() # Keep for debugging if needed, or remove for clean runs.

@pytest.fixture(scope="function")
def set_db_url_env(monkeypatch):
    """Fixture to temporarily set and unset LLM_ACCOUNTING_DB_URL."""
    original_url = os.environ.get("LLM_ACCOUNTING_DB_URL")
    
    def _set_url(url):
        monkeypatch.setenv("LLM_ACCOUNTING_DB_URL", url)
        
    yield _set_url
    
    # Restore original environment variable or unset if it wasn't there
    if original_url is None:
        monkeypatch.delenv("LLM_ACCOUNTING_DB_URL", raising=False)
    else:
        monkeypatch.setenv("LLM_ACCOUNTING_DB_URL", original_url)


@pytest.fixture(scope="function")
def alembic_config(sqlite_db_url): # Default to SQLite for config, can be overridden
    """Provides an AlembicConfig object configured for the test database."""
    # Check if alembic.ini exists at the root. If not, skip tests requiring it.
    if not pathlib.Path("alembic.ini").exists():
        pytest.skip("alembic.ini not found, skipping Alembic direct command tests.")
        
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sqlite_db_url) # Override with test DB URL
    return cfg

# --- Helper Functions ---

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


# --- SQLite Tests ---

def test_sqlite_initial_migration_creates_schema(sqlite_db_url, set_db_url_env, alembic_config):
    logger.info(f"Running test_sqlite_initial_migration_creates_schema with DB URL: {sqlite_db_url}")
    set_db_url_env(sqlite_db_url)

    # 1. Run migrations (simulates LLMAccounting instantiation)
    run_migrations()

    # 2. Create engine and inspect
    engine = create_engine(sqlite_db_url)
    
    # 3. Verify all expected tables exist
    expected_tables = set(Base.metadata.tables.keys())
    logger.info(f"Expected tables: {expected_tables}")
    
    current_tables = set(get_table_names(engine))
    logger.info(f"Current tables in DB: {current_tables}")
    
    assert expected_tables.issubset(current_tables), \
        f"Not all expected tables found. Missing: {expected_tables - current_tables}"

    # 4. Verify alembic_version table and its content
    assert "alembic_version" in current_tables, "alembic_version table not found."
    
    # The `run_migrations` should bring it to head, which is REVISION_ADD_NOTES_COLUMN
    # because that's the latest migration we generated.
    assert get_alembic_revision(engine) == REVISION_ADD_NOTES_COLUMN, \
        f"Alembic version should be at {REVISION_ADD_NOTES_COLUMN} after initial run_migrations."

def test_sqlite_applies_new_migration_and_preserves_data(sqlite_db_url, set_db_url_env, alembic_config):
    logger.info(f"Running test_sqlite_applies_new_migration_and_preserves_data with DB URL: {sqlite_db_url}")
    set_db_url_env(sqlite_db_url)
    engine = create_engine(sqlite_db_url)

    # 1. Baseline: Migrate to the revision *before* "add_notes_column"
    logger.info(f"Upgrading to initial tables revision: {REVISION_INITIAL_TABLES}")
    alembic_command.upgrade(alembic_config, REVISION_INITIAL_TABLES)
    
    current_revision = get_alembic_revision(engine)
    logger.info(f"Revision after initial upgrade: {current_revision}")
    assert current_revision == REVISION_INITIAL_TABLES

    # Verify 'notes' column does NOT exist yet
    accounting_columns_before = get_column_names(engine, "accounting_entries")
    logger.info(f"Columns in accounting_entries before 'add_notes' migration: {accounting_columns_before}")
    assert "notes" not in accounting_columns_before

    # 2. Add dummy data
    logger.info("Adding dummy data to accounting_entries.")
    with engine.connect() as connection:
        # Need to ensure the table object matches the schema at this revision
        # For simplicity, use raw SQL or ensure AccountingEntry model matches this state.
        # Using raw SQL is safer here as model might have 'notes' if not careful with imports.
        stmt = text(
            "INSERT INTO accounting_entries (timestamp, model, cost, execution_time, cached_tokens, reasoning_tokens) "
            "VALUES (:ts, :model, :cost, :exec_time, :cached, :reasoning)"
        )
        connection.execute(
            stmt,
            {
                "ts": "2023-01-01T12:00:00",
                "model": "test-model-1",
                "cost": 1.23,
                "exec_time": 0.5,
                "cached": 0,
                "reasoning": 0
            },
        )
        connection.commit()
        
    # Verify data insertion
    with engine.connect() as connection:
        result = connection.execute(text("SELECT COUNT(*) FROM accounting_entries")).scalar_one()
    assert result == 1, "Dummy data not inserted correctly."
    logger.info("Dummy data inserted.")

    # 3. Run Migrations Again (this should apply the "add_notes_column" migration)
    logger.info("Running migrations again to apply 'add_notes_column'.")
    run_migrations() # This should upgrade to head (REVISION_ADD_NOTES_COLUMN)

    # 4. Verify Schema Update
    current_revision_after_second_run = get_alembic_revision(engine)
    logger.info(f"Revision after second run_migrations: {current_revision_after_second_run}")
    assert current_revision_after_second_run == REVISION_ADD_NOTES_COLUMN
    
    accounting_columns_after = get_column_names(engine, "accounting_entries")
    logger.info(f"Columns in accounting_entries after 'add_notes' migration: {accounting_columns_after}")
    assert "notes" in accounting_columns_after, "'notes' column not found after migration."

    # 5. Verify Data Preservation
    logger.info("Verifying data preservation.")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT model, cost, execution_time FROM accounting_entries WHERE model = 'test-model-1'")
        ).first()
    
    assert row is not None, "Previously inserted row not found."
    assert row._mapping["model"] == "test-model-1"
    assert row._mapping["cost"] == 1.23
    assert abs(row._mapping["execution_time"] - 0.5) < 1e-9 # For float comparison
    logger.info("Data preservation verified.")


# --- PostgreSQL Tests ---

# Environment variable for PostgreSQL connection string for tests
TEST_POSTGRESQL_URL = os.environ.get("TEST_POSTGRESQL_DB_URL")

@pytest.fixture(scope="function")
def postgresql_alembic_config():
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
    
    # Ensure a clean state before the test by dropping all known tables
    # This is simpler than creating/dropping databases/schemas in many test environments
    # It assumes the user/role has permissions to drop tables.
    with engine.connect() as connection:
        # Drop alembic_version first if it exists
        try:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
            connection.commit()
        except Exception as e:
            logger.warning(f"Could not drop alembic_version table during PG cleanup (might not exist): {e}")

        # Drop all other tables defined in Base.metadata
        # Iterate in reverse order of table creation dependency
        for table in reversed(Base.metadata.sorted_tables):
            try:
                table.drop(connection, checkfirst=True) # checkfirst=True avoids error if table doesn't exist
                logger.info(f"Dropped table {table.name} for PG test setup.")
            except Exception as e: # Catch more general exceptions as different DBs might raise different errors
                logger.warning(f"Could not drop table {table.name} during PG cleanup (might not exist or other issue): {e}")
        connection.commit()
        
    yield engine
    
    # Teardown (optional, could also clean after, but cleaning before is often safer for retries)
    # engine.dispose() # Not strictly necessary for function scope if connection is managed

@pytest.mark.skipif(not TEST_POSTGRESQL_URL, reason="TEST_POSTGRESQL_DB_URL not set")
def test_postgresql_initial_migration_creates_schema(postgresql_engine, set_db_url_env, postgresql_alembic_config):
    logger.info(f"Running test_postgresql_initial_migration_creates_schema with DB URL: {TEST_POSTGRESQL_URL}")
    set_db_url_env(TEST_POSTGRESQL_URL)

    run_migrations()

    expected_tables = set(Base.metadata.tables.keys())
    current_tables = set(get_table_names(postgresql_engine))
    logger.info(f"Expected tables (PG): {expected_tables}")
    logger.info(f"Current tables in DB (PG): {current_tables}")
    
    assert expected_tables.issubset(current_tables), \
        f"Not all expected tables found in PG. Missing: {expected_tables - current_tables}"
    
    assert "alembic_version" in current_tables, "alembic_version table not found in PG."
    assert get_alembic_revision(postgresql_engine) == REVISION_ADD_NOTES_COLUMN, \
        f"Alembic version in PG should be at {REVISION_ADD_NOTES_COLUMN}."

@pytest.mark.skipif(not TEST_POSTGRESQL_URL, reason="TEST_POSTGRESQL_DB_URL not set")
def test_postgresql_applies_new_migration_and_preserves_data(postgresql_engine, set_db_url_env, postgresql_alembic_config):
    logger.info(f"Running test_postgresql_applies_new_migration_and_preserves_data with DB URL: {TEST_POSTGRESQL_URL}")
    set_db_url_env(TEST_POSTGRESQL_URL)

    # 1. Baseline: Migrate to the revision *before* "add_notes_column"
    logger.info(f"Upgrading PG to initial tables revision: {REVISION_INITIAL_TABLES}")
    alembic_command.upgrade(postgresql_alembic_config, REVISION_INITIAL_TABLES)
    assert get_alembic_revision(postgresql_engine) == REVISION_INITIAL_TABLES
    
    accounting_columns_before = get_column_names(postgresql_engine, "accounting_entries")
    assert "notes" not in accounting_columns_before

    # 2. Add dummy data
    logger.info("Adding dummy data to PG accounting_entries.")
    with postgresql_engine.connect() as connection:
        stmt = text(
            "INSERT INTO accounting_entries (timestamp, model, cost, execution_time, cached_tokens, reasoning_tokens) "
            "VALUES (:ts, :model, :cost, :exec_time, :cached, :reasoning)"
        )
        connection.execute(
            stmt,
            {
                "ts": datetime(2023, 1, 1, 12, 0, 0), # Use datetime object for PG
                "model": "pg-test-model-1",
                "cost": 4.56,
                "exec_time": 0.7,
                "cached": 0,
                "reasoning": 0
            },
        )
        connection.commit()

    with postgresql_engine.connect() as connection:
        result = connection.execute(text("SELECT COUNT(*) FROM accounting_entries")).scalar_one()
    assert result == 1, "Dummy data not inserted correctly in PG."
    logger.info("Dummy data inserted in PG.")

    # 3. Run Migrations Again
    logger.info("Running migrations again on PG to apply 'add_notes_column'.")
    run_migrations()

    # 4. Verify Schema Update
    assert get_alembic_revision(postgresql_engine) == REVISION_ADD_NOTES_COLUMN
    accounting_columns_after = get_column_names(postgresql_engine, "accounting_entries")
    assert "notes" in accounting_columns_after, "'notes' column not found in PG after migration."

    # 5. Verify Data Preservation
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

# Example of how to run tests with PostgreSQL:
# TEST_POSTGRESQL_DB_URL="postgresql://user:pass@host:port/testdbname" pytest -s -k postgresql
# Ensure the test database exists and the user has permissions to create/drop tables in it,
# or at least within the default schema of that database.
# The postgresql_engine fixture attempts to clean tables before each test.
# If permissions are restrictive, manual schema/db setup might be needed before running.
# For CI, often a dedicated test DB is created, and the URL is passed via env vars.
# The current PG tests drop/recreate tables, so they should not be run against a production DB.
# If alembic.ini is not at project root, adjust AlembicConfig path or set script_location.
# `pytest -s` shows print statements (and log output if configured).
# `pytest -k postgresql` runs only tests with 'postgresql' in their name.
# `pytest --log-cli-level=INFO` can also show logs.

# To make this test file runnable:
# 1. Ensure `alembic.ini` is in the project root (or adjust path in `AlembicConfig`).
# 2. Ensure the `src` directory is importable (e.g., by running pytest from the project root,
#    or by having `PYTHONPATH` set up correctly if running from elsewhere).
# 3. For PostgreSQL tests, set the `TEST_POSTGRESQL_DB_URL` environment variable.
#    Example: export TEST_POSTGRESQL_DB_URL="postgresql://postgres:password@localhost:5432/test_llm_accounting"
#    The user needs permission to connect and ideally to create/drop tables in that database.
#    The `postgresql_engine` fixture will attempt to drop all known tables before each test run.
#    If the database or user doesn't allow dropping tables, manual cleanup or a different
#    setup strategy for PG tests might be needed.
#    A common strategy for CI is to have a script that creates a temporary test DB,
#    runs tests, and then drops it.
#    If running locally, ensure your PG server is running and accessible.
#    The tests are written to be mostly self-contained if the DB URL and permissions are correct.

# Final check on imports and structure:
# - alembic_config fixture relies on sqlite_db_url by default but postgresql_alembic_config uses TEST_POSTGRESQL_URL.
# - set_db_url_env fixture is used to set LLM_ACCOUNTING_DB_URL for run_migrations().
# - Helper functions for table/column names and revision are defined.
# - Tests for SQLite and PostgreSQL follow similar patterns.
# - PostgreSQL tests are skipped if TEST_POSTGRESQL_DB_URL is not set.
# - PostgreSQL setup fixture attempts to clean tables for a consistent test environment.
# - The test for initial migration checks against REVISION_ADD_NOTES_COLUMN because run_migrations() brings to head.
# - The test for applying new migration correctly uses alembic_command.upgrade() to go to a specific prior revision.
