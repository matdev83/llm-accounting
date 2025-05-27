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
        project TEXT DEFAULT NULL,
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
                  remote_completion_id: Optional[str] = None, project: Optional[str] = None,
                  timestamp: Optional[datetime] = None):
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
                response_text, remote_completion_id, project, log_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, app_name, user_name, model, prompt_text,
              response_text, remote_completion_id, project, log_type))
        self.conn.commit()

    def log_prompt(self, app_name: str, user_name: str, model: str, prompt_text: str,
                   project: Optional[str] = None, timestamp: Optional[datetime] = None):
        """
        Logs a prompt event to the audit log.
        """
        if self.conn is None:
            raise ConnectionError("Database connection is not open. Call connect() or use a context manager.")

        cursor = self.conn.cursor()
        ts = timestamp.isoformat() if timestamp else datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, prompt_text, project, log_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, app_name, user_name, model, prompt_text, project, 'prompt'))
        self.conn.commit()

    def log_response(self, app_name: str, user_name: str, model: str, response_text: str,
                     remote_completion_id: Optional[str] = None, project: Optional[str] = None,
                     timestamp: Optional[datetime] = None):
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
                remote_completion_id, project, log_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts, app_name, user_name, model, response_text,
              remote_completion_id, project, 'response'))
        self.conn.commit()

    def get_db_path(self) -> str:
        """
        Returns the database path of the AuditLogger.
        """
        return self.db_path
