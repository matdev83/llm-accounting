import logging
import re
from typing import Dict, List
from sqlalchemy import text

logger = logging.getLogger(__name__)


class SQLiteQueryExecutor:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def execute_query(self, query: str) -> List[Dict]:
        """
        Execute a raw SQL SELECT query and return results.
        """
        clean_query = query.strip()
        if ";" in clean_query[:-1]:
            raise ValueError("Semicolons are not allowed in custom queries.")
        if clean_query.endswith(";"):
            clean_query = clean_query[:-1]

        if not clean_query.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed.")
        if re.search(r"\b(PRAGMA|ATTACH|ALTER|CREATE|INSERT|UPDATE|DELETE|DROP|REPLACE|GRANT|REVOKE)\b", clean_query, re.IGNORECASE):
            raise ValueError("Only read-only SELECT statements are allowed.")

        conn = self.connection_manager.get_connection()
        try:
            result = conn.execute(text(query))
            results = [dict(row._mapping) for row in result.fetchall()]
            return results
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e
