import logging

class MockQueryExecutor:
    def __init__(self, parent_backend):
        self.parent_backend = parent_backend

    def execute_query(self, query: str) -> list[dict]:
        """Mocks executing a raw SQL SELECT query."""
        logging.debug(f"MockBackend: Executing query: {query}")
        if query.strip().upper().startswith("SELECT"):
            return [
                {"id": 1, "model": "mock_model_A", "tokens": 100},
                {"id": 2, "model": "mock_model_B", "tokens": 200},
            ]
        raise ValueError("MockBackend only supports SELECT queries for execute_query.")
