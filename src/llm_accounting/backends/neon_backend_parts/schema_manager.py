import logging
import psycopg2

logger = logging.getLogger(__name__)

class SchemaManager:
    def __init__(self, backend_instance):
        self.backend = backend_instance

    def _create_schema_if_not_exists(self) -> None:
        """
        Ensures the necessary database schema (tables) exists.
        """
        self._create_tables()

    def _create_tables(self) -> None:
        """
        Creates the database tables (`accounting_entries`, `usage_limits`)
        if they do not already exist in the PostgreSQL database.

        Uses `CREATE TABLE IF NOT EXISTS` to avoid errors if tables are already present.
        The schema is designed to store usage data, and limits,
        mapping directly to the `UsageEntry`, and `UsageLimit` dataclasses.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during DDL execution (and is re-raised).
            Exception: For any other unexpected errors during table creation (and is re-raised).
        """
        try:
            self.backend._ensure_connected() # Use the backend's ensure_connected
            assert self.backend.conn is not None # Pylance: self.conn is guaranteed to be not None here.

            # SQL DDL commands for creating tables.
            # These correspond to UsageEntry, and UsageLimit dataclasses.
            commands = (
                """
                CREATE TABLE IF NOT EXISTS accounting_entries (
                    id SERIAL PRIMARY KEY, -- Auto-incrementing integer primary key
                    model_name VARCHAR(255) NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    local_prompt_tokens INTEGER,
                    local_completion_tokens INTEGER,
                    local_total_tokens INTEGER,
                    project TEXT DEFAULT NULL,
                    cost DOUBLE PRECISION NOT NULL,       -- Cost of the API call
                    execution_time DOUBLE PRECISION,      -- Execution time in seconds
                    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Timestamp of the entry
                    caller_name VARCHAR(255),             -- Optional identifier for the calling function/module
                    username VARCHAR(255),                -- Optional identifier for the user
                    cached_tokens INTEGER,                -- Number of tokens retrieved from cache
                    reasoning_tokens INTEGER              -- Number of tokens used for reasoning/tool use
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS usage_limits (
                    id SERIAL PRIMARY KEY,
                    scope VARCHAR(50) NOT NULL,           -- e.g., 'USER', 'GLOBAL', 'MODEL' (maps to LimitScope enum)
                    limit_type VARCHAR(50) NOT NULL,      -- e.g., 'COST', 'REQUESTS', 'TOKENS' (maps to LimitType enum)
                    max_value DOUBLE PRECISION NOT NULL,  -- Maximum value for the limit
                    interval_unit VARCHAR(50) NOT NULL,   -- e.g., 'HOURLY', 'DAILY', 'MONTHLY' (maps to LimitIntervalUnit enum)
                    interval_value INTEGER NOT NULL,      -- Numerical value for the interval (e.g., 1 for monthly)
                    model_name VARCHAR(255),              -- Specific model this limit applies to (optional)
                    username VARCHAR(255),                -- Specific user this limit applies to (optional)
                    caller_name VARCHAR(255),             -- Specific caller this limit applies to (optional)
                    project_name TEXT DEFAULT NULL,       -- Specific project this limit applies to (optional)
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # A cursor is obtained to execute SQL commands.
            # The `with` statement ensures the cursor is closed automatically.
            with self.backend.conn.cursor() as cur:
                for command in commands:
                    cur.execute(command)
                self.backend.conn.commit() # Commit the transaction to make table creations permanent.
            logger.info("Database tables (accounting_entries, usage_limits) checked/created successfully.")
        except ConnectionError as e:
            logger.error(f"Connection error during table creation: {e}")
            raise # Re-raise the connection error
        except psycopg2.Error as e:
            logger.error(f"Error during table creation: {e}")
            if self.backend.conn and not self.backend.conn.closed: # Check if connection is still valid before rollback
                self.backend.conn.rollback() # Rollback transaction on any DDL error.
            raise  # Re-raise the psycopg2.Error to allow higher-level handling.
        except Exception as e: # Catch any other unexpected exceptions.
            logger.error(f"An unexpected error occurred during table creation: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise # Re-raise the unexpected exception.
