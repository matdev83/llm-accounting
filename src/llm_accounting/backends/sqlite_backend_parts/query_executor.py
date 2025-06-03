import logging
from typing import Dict, List, Any
from sqlalchemy import text

logger = logging.getLogger(__name__)

class SQLiteQueryExecutor:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def execute_query(self, query: str) -> List[Dict]:
        """
        Execute a raw SQL SELECT query and return results.
        """
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed.")

        conn = self.connection_manager.get_connection()
        try:
            result = conn.execute(text(query))
            results = [dict(row._mapping) for row in result.fetchall()]
            return results
        except Exception as e:
            raise RuntimeError(f"Database error: {e}") from e
