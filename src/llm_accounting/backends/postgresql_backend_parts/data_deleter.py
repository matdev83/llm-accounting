import logging
import psycopg2

logger = logging.getLogger(__name__)


class DataDeleter:
    def __init__(self, backend_instance):
        self.backend = backend_instance

    def delete_usage_limit(self, limit_id: int) -> None:
        """
        Deletes a usage limit entry by its ID from the usage_limits table.

        Args:
            limit_id: The ID of the usage limit to delete.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

        sql = "DELETE FROM usage_limits WHERE id = %s;"
        try:
            with self.backend.conn.cursor() as cur:
                cur.execute(sql, (limit_id,))
                self.backend.conn.commit()
            logger.info(f"Successfully deleted usage limit with ID: {limit_id}.")
        except psycopg2.Error as e:
            logger.error(f"Error deleting usage limit: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred deleting usage limit: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise

    def purge(self) -> None:
        """
        Deletes all data from `accounting_entries`, and `usage_limits` tables.

        This is a destructive operation and should be used with caution.
        It iterates through a list of table names and executes a `DELETE FROM` statement for each.
        The operations are performed within a single transaction.

        Raises:
            ConnectionError: If the database connection is not active.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self.backend._ensure_connected()
        assert self.backend.conn is not None  # Pylance: self.conn is guaranteed to be not None here.

        tables_to_purge = ["accounting_entries", "usage_limits"]
        try:
            with self.backend.conn.cursor() as cur:
                for table in tables_to_purge:
                    # Using f-string for table name is generally safe if table names are controlled internally.
                    # TRUNCATE TABLE could be faster but might have locking implications or issues with foreign keys if they existed.
                    # DELETE FROM is safer in general-purpose code.
                    cur.execute(f"DELETE FROM {table};")  # nosec B608
                self.backend.conn.commit()  # Commit transaction after all deletes are successful.
            logger.info(f"Successfully purged data from tables: {', '.join(tables_to_purge)}.")
        except psycopg2.Error as e:
            logger.error(f"Error purging data: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()  # Rollback if any delete operation fails.
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred purging data: {e}")
            if self.backend.conn and not self.backend.conn.closed:
                self.backend.conn.rollback()
            raise
