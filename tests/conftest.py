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

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def temp_db_path(request):
    """Create a temporary database file and return its path, ensuring deletion"""
    # Use delete=False initially to get the path, then manually delete in finalizer
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


@pytest.fixture
def sqlite_backend(temp_db_path):
    """Create and initialize a SQLite backend with a temporary database"""
    backend = SQLiteBackend(db_path=temp_db_path)
    logger.info(f"Initializing SQLiteBackend with db_path: {temp_db_path}")
    backend.initialize()
    logger.info(f"Initialized SQLiteBackend with db_path: {temp_db_path}")
    try:
        yield backend
    finally:
        backend.close()


@pytest.fixture
def accounting(sqlite_backend):
    """Create an LLMAccounting instance with a temporary SQLite backend"""
    acc = LLMAccounting(backend=sqlite_backend)
    acc.__enter__()  # Manually enter the context
    yield acc
    acc.__exit__(None, None, None)  # Manually exit the context


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
    # Mock initialize and close methods if they are called
    mock_backend_instance.initialize.return_value = None
    mock_backend_instance.close.return_value = None
    yield mock_backend_instance
