import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from llm_accounting.backends.sqlite import SQLiteBackend

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    """Create and initialize a SQLite backend with a temporary database"""
    backend = SQLiteBackend(db_path=temp_db_path)
    logger.info(f"Initializing SQLiteBackend with db_path: {temp_db_path}")
    backend.initialize()
    logger.info(f"Initialized SQLiteBackend with db_path: {temp_db_path}")
    try:
        yield backend
    finally:
        backend.close()

@pytest.fixture(scope="class")
def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
