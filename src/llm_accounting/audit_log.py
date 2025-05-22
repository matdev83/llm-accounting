import sqlite3
import pathlib
from typing import Optional
from datetime import datetime, timezone

def initialize_audit_db_schema(conn: sqlite3.Connection):
    """
    Initializes the audit_log_entries table in the database.
    """
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        app_name TEXT NOT NULL,
        user_name TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_text TEXT,
        response_text TEXT,
        remote_completion_id TEXT,
        log_type TEXT NOT NULL CHECK(log_type IN ('prompt', 'response'))
    )
    """)
    conn.commit()

class AuditLogger:
    """
    A class for logging audit trail entries to an SQLite database.
    """
    def __init__(self, db_path: Optional[str] = None):
        """
        Initializes the AuditLogger.

        Args:
            db_path: Optional path to the SQLite database file.
                     Defaults to "data/audit_log.sqlite".
        """
        self.db_path = db_path if db_path is not None else "data/audit_log.sqlite"
        self.conn: Optional[sqlite3.Connection] = None

        # Ensure the parent directory for db_path exists
        path = pathlib.Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """
        Establishes a connection to the SQLite database.
        Initializes the schema if the table doesn't exist.
        """
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            initialize_audit_db_schema(self.conn)
        return self.conn

    def close(self):
        """
        Closes the database connection if it's open.
        """
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """
        Context manager entry point. Connects to the database.
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point. Closes the database connection.
        """
        self.close()

    # Generic log_event method (can be kept or removed if specific methods are preferred)
    def log_event(self, app_name: str, user_name: str, model: str, log_type: str,
                  prompt_text: Optional[str] = None, response_text: Optional[str] = None,
                  remote_completion_id: Optional[str] = None, timestamp: Optional[datetime] = None):
        """
        Logs an event to the audit log.
        """
        if self.conn is None:
             raise ConnectionError("Database connection is not open. Call connect() or use a context manager.")


        cursor = self.conn.cursor()
        # Use datetime.now(timezone.UTC) if timestamp is None
        ts = timestamp.isoformat() if timestamp else datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, prompt_text,
                response_text, remote_completion_id, log_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, app_name, user_name, model, prompt_text,
              response_text, remote_completion_id, log_type))
        self.conn.commit()

    def log_prompt(self, app_name: str, user_name: str, model: str, prompt_text: str, timestamp: Optional[datetime] = None):
        """
        Logs a prompt event to the audit log.
        """
        if self.conn is None:
             raise ConnectionError("Database connection is not open. Call connect() or use a context manager.")

        cursor = self.conn.cursor()
        ts = timestamp.isoformat() if timestamp else datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, prompt_text, log_type
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (ts, app_name, user_name, model, prompt_text, 'prompt'))
        self.conn.commit()

    def log_response(self, app_name: str, user_name: str, model: str, response_text: str,
                     remote_completion_id: Optional[str] = None, timestamp: Optional[datetime] = None):
        """
        Logs a response event to the audit log.
        """
        if self.conn is None:
             raise ConnectionError("Database connection is not open. Call connect() or use a context manager.")

        cursor = self.conn.cursor()
        ts = timestamp.isoformat() if timestamp else datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, response_text,
                remote_completion_id, log_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, app_name, user_name, model, response_text,
              remote_completion_id, 'response'))
        self.conn.commit()

# if __name__ == '__main__':
#     # Example Usage
#     default_db_file = "data/audit_log_main.sqlite"
#     custom_db_file = "data/custom_audit_main.sqlite"

#     # Clean up previous example DB files if they exist
#     pathlib.Path(default_db_file).unlink(missing_ok=True)
#     pathlib.Path(custom_db_file).unlink(missing_ok=True)

#     logger = AuditLogger(db_path=default_db_file)

#     # Using the context manager for log_event
#     with logger as db_logger:
#         print(f"Connected to DB: {db_logger.db_path} (context manager)")
#         db_logger.log_event(
#             app_name="example_app_ctx",
#             user_name="test_user_ctx",
#             model="gpt-test-ctx",
#             log_type="prompt",
#             prompt_text="This is a test prompt via log_event (ctx)."
#         )
#         db_logger.log_event(
#             app_name="example_app_ctx",
#             user_name="test_user_ctx",
#             model="gpt-test-ctx",
#             log_type="response",
#             response_text="This is a test response via log_event (ctx).",
#             remote_completion_id="cmpl-ctx"
#         )
#         print("Logged a prompt and a response via log_event (context manager).")

#     # Using new methods (manual connect/close pattern, though connect is called internally)
#     print(f"\nTesting log_prompt and log_response with: {logger.db_path}")
#     logger.log_prompt(
#         app_name="app_manual",
#         user_name="user_manual_prompt",
#         model="gpt-4",
#         prompt_text="What is the capital of France?"
#     )
#     print("Logged a prompt via log_prompt.")

#     logger.log_response(
#         app_name="app_manual",
#         user_name="user_manual_response",
#         model="gpt-4",
#         response_text="The capital of France is Paris.",
#         remote_completion_id="cmpl-manual123"
#     )
#     print("Logged a response via log_response.")

#     # Verify content of default DB
#     conn_default = sqlite3.connect(default_db_file)
#     cursor_default = conn_default.cursor()
#     cursor_default.execute("SELECT * FROM audit_log_entries ORDER BY id")
#     rows_default = cursor_default.fetchall()
#     print(f"\nFound {len(rows_default)} entries in '{default_db_file}':")
#     for row in rows_default:
#         print(row)
#     conn_default.close()


#     # Example with a custom db_path and new methods
#     custom_logger = AuditLogger(db_path=custom_db_file)
#     print(f"\nTesting log_prompt and log_response with custom DB: {custom_logger.db_path}")
#     # Using context manager for custom logger
#     with custom_logger as cl:
#         cl.log_prompt(
#             app_name="custom_app_1",
#             user_name="custom_user_A",
#             model="claude-opus",
#             prompt_text="Explain black holes."
#         )
#         cl.log_response(
#             app_name="custom_app_1",
#             user_name="custom_user_A",
#             model="claude-opus",
#             response_text="A black hole is a region of spacetime where gravity is so strong that nothing...",
#             remote_completion_id="cmpl-claude1"
#         )
#     print("Logged to custom DB via new methods using context manager.")

#     # Log another event without context manager to test auto-connect
#     custom_logger.log_prompt(
#         app_name="custom_app_2",
#         user_name="custom_user_B",
#         model="gemini-pro",
#         prompt_text="What is photosynthesis?",
#         # Providing a specific timestamp
#         timestamp=datetime(2023, 10, 26, 10, 30, 0)
#     )
#     print("Logged another prompt to custom DB (manual call).")


#     # Verify custom DB content
#     conn_custom = sqlite3.connect(custom_db_file)
#     cursor_custom = conn_custom.cursor()
#     cursor_custom.execute("SELECT * FROM audit_log_entries ORDER BY id")
#     rows_custom = cursor_custom.fetchall()
#     print(f"\nFound {len(rows_custom)} entries in '{custom_db_file}':")
#     for row in rows_custom:
#         print(row)
#     conn_custom.close()

#     # Clean up the created database files for the example
#     pathlib.Path(default_db_file).unlink(missing_ok=True)
#     pathlib.Path(custom_db_file).unlink(missing_ok=True)
#     try:
#         # Remove data directory only if it's empty and was created by this script.
#         # This is a bit fragile for a general test.
#         if not any(pathlib.Path("data").iterdir()):
#              pathlib.Path("data").rmdir()
#              print("\nCleaned up data directory.")
#         else:
#             print("\nData directory not empty or not created by this script, not removing.")
#     except FileNotFoundError:
#         print("\nData directory not found, no cleanup needed for it.")
#     except OSError as e:
#         print(f"\nData directory not empty or other error during cleanup: {e}")
