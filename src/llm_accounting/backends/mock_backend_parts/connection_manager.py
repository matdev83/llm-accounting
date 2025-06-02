import logging

class MockConnectionManager:
    def __init__(self, parent_backend):
        self.parent_backend = parent_backend

    def _ensure_connected(self) -> None:
        """Mocks ensuring connection."""
        pass

    def initialize(self) -> None:
        """Mocks the initialization of the backend."""
        self.parent_backend.initialized = True
        logging.debug("MockBackend initialized.")

    def close(self) -> None:
        """Mocks closing any open connections."""
        self.parent_backend.closed = True
        logging.debug("MockBackend closed.")
