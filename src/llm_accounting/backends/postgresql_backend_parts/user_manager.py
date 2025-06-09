import logging
from datetime import datetime
from typing import List, Dict

class UserManager:
    def __init__(self, backend_instance):
        self.backend = backend_instance
        self.logger = logging.getLogger(__name__)

    def create_user(self, user_name: str, ou_name: str | None = None, email: str | None = None) -> None:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_name, ou_name, email, created_at, last_enabled_at, enabled)"
                " VALUES (%s, %s, %s, %s, %s, TRUE)",
                (user_name, ou_name, email, datetime.utcnow(), datetime.utcnow()),
            )
        self.backend.conn.commit()

    def list_users(self) -> List[Dict]:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute("SELECT id, user_name, ou_name, email, created_at, last_enabled_at, last_disabled_at, enabled FROM users ORDER BY user_name")
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]

    def update_user(self, user_name: str, new_name: str) -> None:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute("UPDATE users SET user_name = %s WHERE user_name = %s", (new_name, user_name))
        self.backend.conn.commit()

    def set_user_active(self, user_name: str, active: bool) -> None:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        field = "last_enabled_at" if active else "last_disabled_at"
        with self.backend.conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {field} = %s, enabled = %s WHERE user_name = %s",
                (datetime.utcnow(), active, user_name),
            )
        self.backend.conn.commit()
