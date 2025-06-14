import logging
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


class SQLiteQuotaRejectionManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def log_rejection(self, conn: Connection, session: str, rejection_message: str, created_at: datetime) -> None:
        query = text(
            "INSERT INTO quota_rejections (created_at, session, rejection_message)"
            " VALUES (:created_at, :session, :rejection_message)"
        )
        conn.execute(
            query,
            {
                "created_at": created_at.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.%f'),
                "session": session,
                "rejection_message": rejection_message,
            },
        )

    # TODO: Vulture - verify and remove if truly dead code.
    # def initialize_schema(self) -> None:
    #     logger.info("Quota rejection schema is initialized as part of migrations")
