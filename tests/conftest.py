import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llm_accounting import LLMAccounting, UsageEntry, UsageStats
from llm_accounting.backends.sqlite import SQLiteBackend
from tests.backends.mock_backends import MockBackend

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# This line is commented out as it might conflict with tox's path management or standard Python packaging.

# Attempt to fix "Table already defined" error by clearing metadata once per session
try:
    from llm_accounting.models.base import Base
    Base.metadata.clear()
    logging.getLogger(__name__).info("Cleared SQLAlchemy Base.metadata at the start of the test session (tests/conftest.py module level).")
except ImportError:
    logging.getLogger(__name__).warning("Could not import Base from llm_accounting.models.base to clear metadata in tests/conftest.py.")
except Exception as e:
    logging.getLogger(__name__).error(f"Error clearing metadata in tests/conftest.py: {e}")

logging.basicConfig(level=logging.INFO) # Ensure logging is configured
logger = logging.getLogger(__name__)

@pytest.fixture(scope="session", autouse=True)
def clear_metadata_globally_once_for_session():
    """
    Ensures metadata is cleared once at the beginning of the test session.
    The actual clearing is done at the module level when this conftest.py is first imported.
    """
    pass

@pytest.fixture(scope="class")
def temp_db_path(request):
    """Create a temporary database file and return its path, ensuring deletion"""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        db_path = tmp.name
        logger.info(f"Created temporary database file: {db_path}")

    def cleanup():
        logger.info(f"Attempting to delete temporary database file: {db_path}")
        try:
            os.remove(db_path)
            logger.info(f"Successfully deleted temporary database file: {db_path}")
        except OSError as e:
            logger.error(f"Error deleting temporary database file {db_path}: {e}")

    request.addfinalizer(cleanup)
    return db_path

@pytest.fixture(scope="class")
def sqlite_backend(temp_db_path):
    """Create a SQLite backend instance with a temporary database. Initialization is deferred."""
    backend = SQLiteBackend(db_path=temp_db_path)
    logger.info(f"SQLiteBackend instance created with db_path: {temp_db_path}. Initialization deferred.")
    try:
        yield backend
    finally:
        if backend.conn or backend.engine:
            logger.info(f"Closing SQLiteBackend for db_path: {temp_db_path}")
            backend.close()
        else:
            logger.info(f"SQLiteBackend for {temp_db_path} was not connected/initialized, no close needed.")

@pytest.fixture
def accounting(sqlite_backend, request):
    """Create an LLMAccounting instance with a temporary SQLite backend, ensuring migrations run."""
    db_url_for_migrations = f"sqlite:///{sqlite_backend.db_path}"
    original_env_url = os.environ.get("LLM_ACCOUNTING_DB_URL")
    db_url_was_set_by_this_fixture = False

    if not original_env_url:
        logger.info(f"accounting fixture: LLM_ACCOUNTING_DB_URL not set. Setting to {db_url_for_migrations} for migrations via LLMAccounting.__init__.")
        os.environ["LLM_ACCOUNTING_DB_URL"] = db_url_for_migrations
        db_url_was_set_by_this_fixture = True
    else:
        logger.info(f"accounting fixture: LLM_ACCOUNTING_DB_URL already set to {original_env_url}. Using it for migrations.")

    acc = LLMAccounting(backend=sqlite_backend)
    acc.__enter__()
    
    try:
        yield acc
    finally:
        acc.__exit__(None, None, None)
        if db_url_was_set_by_this_fixture:
            logger.info(f"accounting fixture: Clearing LLM_ACCOUNTING_DB_URL that was set by this fixture.")
            del os.environ["LLM_ACCOUNTING_DB_URL"]
        elif original_env_url:
             os.environ["LLM_ACCOUNTING_DB_URL"] = original_env_url

@pytest.fixture
def sample_entries():
    """Create sample usage entries for testing"""
    now = datetime.now()
    return [
        UsageEntry(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.002,
            execution_time=1.5,
            timestamp=now - timedelta(hours=2)
        ),
        UsageEntry(
            model="gpt-3.5-turbo",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.001,
            execution_time=0.8,
            timestamp=now - timedelta(hours=1)
        ),
        UsageEntry(
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
            cost=0.003,
            execution_time=2.0,
            timestamp=now
        )
    ]

@pytest.fixture
def mock_backend():
    """Create a mock backend instance"""
    mock_backend_instance = MagicMock()
    mock_backend_instance.initialize.return_value = None
    mock_backend_instance.close.return_value = None
    yield mock_backend_instance
