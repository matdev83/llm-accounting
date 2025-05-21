import sqlite3
from datetime import datetime
from pathlib import Path
import time
from typing import Dict, List, Tuple, Optional

from .base import BaseBackend, UsageEntry, UsageStats
from .sqlite_utils import validate_db_filename, initialize_db_schema
from .sqlite_queries import get_period_stats_query, get_model_stats_query, get_model_rankings_query, tail_query, insert_usage_query

import logging

logger = logging.getLogger(__name__)


class SQLiteBackend(BaseBackend):
    """SQLite implementation of the usage tracking backend"""

    def __init__(self, db_path: Optional[str] = None):
        actual_db_path = db_path if db_path is not None else 'data/accounting.sqlite'
        validate_db_filename(actual_db_path)
        self.db_path = actual_db_path  # Store as string
        if not self.db_path.startswith("file:"):
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        """Initialize the SQLite database"""
        if str(self.db_path).startswith("file:"):
            self.conn = sqlite3.connect(self.db_path, uri=True)
        else:
            self.conn = sqlite3.connect(self.db_path)
        initialize_db_schema(self.conn)

    def insert_usage(self, entry: UsageEntry) -> None:
        """Insert a new usage entry into the database"""
        assert self.conn is not None
        insert_usage_query(self.conn, entry)

    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        """Get aggregated statistics for a time period"""
        assert self.conn is not None
        return get_period_stats_query(self.conn, start, end)

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        """Get statistics grouped by model for a time period"""
        assert self.conn is not None
        return get_model_stats_query(self.conn, start, end)

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, float]]]:
        """Get model rankings based on different metrics"""
        assert self.conn is not None
        return get_model_rankings_query(self.conn, start, end)

    def purge(self) -> None:
        """Delete all usage entries from the database"""
        assert self.conn is not None
        self.conn.execute("DELETE FROM accounting_entries")
        self.conn.commit()

    def tail(self, n: int = 10) -> List[UsageEntry]:
        """Get the n most recent usage entries"""
        assert self.conn is not None
        return tail_query(self.conn, n)

    def close(self) -> None:
        """Close the database connection"""
        if self.conn:
            logger.info(f"Attempting to close sqlite connection for {self.db_path}")
            self.conn.close()
            logger.info(f"sqlite connection closed for {self.db_path}")
            self.conn = None
            logger.info(f"self.conn set to None for {self.db_path}")
            # Add a small delay to allow the OS to release the file handle
            time.sleep(0.01)
        else:
            logger.info(f"No sqlite connection to close for {self.db_path}")

    def execute_query(self, query: str) -> List[Dict]:
        """Execute a raw SQL SELECT query and return results"""
        if not self.conn:
            self.initialize()
            
        assert self.conn is not None  # For type checking
        try:
            cursor = self.conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error: {e}") from e
