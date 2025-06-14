import logging
import psycopg2

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, backend_instance):
        self.backend = backend_instance
        self.connection_string = backend_instance.connection_string

    def initialize(self) -> None:
        """
        Connects to the PostgreSQL database and sets up the schema.

        Raises:
            ConnectionError: If the connection to the database fails during `psycopg2.connect`
                             or if schema creation fails.
        """
        try:
            logger.info("Attempting to connect to PostgreSQL database "
                        "using the provided connection string.")
            # Establish the connection to the PostgreSQL database.
            self.backend.conn = psycopg2.connect(self.connection_string)
            logger.info("Successfully connected to PostgreSQL database.")
            # Ensure the necessary database schema (tables) exists.
            # This part will be moved to SchemaManager, but for now, keep it here
            # to avoid breaking the current flow until all parts are refactored.
            # self.backend._create_schema_if_not_exists()
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL database: {e}")
            self.backend.conn = None  # Ensure conn is None if connection failed
            # The original psycopg2.Error 'e' is included in the ConnectionError for more detailed debugging.
            raise ConnectionError("Failed to connect to PostgreSQL database "
                                  "(see logs for details).") from e

    def close(self) -> None:
        """
        Closes the connection to the PostgreSQL database.
        """
        if self.backend.conn and not self.backend.conn.closed:
            self.backend.conn.close()
            logger.info("Closed connection to PostgreSQL database.")
        else:
            logger.info("Connection to PostgreSQL database was already closed or not established.")
        self.backend.conn = None

    def ensure_connected(self) -> None:
        """
        Ensures the PostgreSQL backend has an active connection.
        Initializes the connection if it's None or closed.
        Raises ConnectionError if initialization fails.
        """
        if self.backend.conn is None or self.backend.conn.closed:
            try:
                self.initialize()
            except ConnectionError as e:
                logger.error(f"Failed to establish connection in ensure_connected: {e}")
                raise  # Re-raise the connection error
