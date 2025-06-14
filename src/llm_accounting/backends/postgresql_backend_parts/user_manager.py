import logging
from typing import List
from datetime import datetime, timezone


class UserManager:
    def __init__(self, backend_instance):
        self.backend = backend_instance
        self.logger = logging.getLogger(__name__)

    def create_user(self, user_name: str, ou_name=None, email=None, enabled=True) -> None:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_name, ou_name, email, enabled) VALUES (%s, %s, %s, %s)",
                (user_name, ou_name, email, enabled),
            )
        self.backend.conn.commit()

    def list_users(self) -> List[dict]:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_name, ou_name, email, created_at, last_enabled_at, last_disabled_at, enabled "
                "FROM users ORDER BY user_name"
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def update_user(self, user_name: str, new_user_name=None, ou_name=None, email=None, enabled=None) -> None:
        fields = []
        params = []
        if new_user_name is not None:
            fields.append("user_name = %s")
            params.append(new_user_name)
        if ou_name is not None:
            fields.append("ou_name = %s")
            params.append(ou_name)
        if email is not None:
            fields.append("email = %s")
            params.append(email)
        ts = datetime.now(timezone.utc)
        if enabled is not None:
            fields.append("enabled = %s")
            params.append(enabled)
            if enabled:
                fields.append("last_enabled_at = %s")
                params.append(ts)
            else:
                fields.append("last_disabled_at = %s")
                params.append(ts)
        if not fields:
            return
        query = "UPDATE users SET " + ", ".join(fields) + " WHERE user_name = %s"  # nosec B608
        params.append(user_name)
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute(query, params)
        self.backend.conn.commit()

    def set_user_enabled(self, user_name: str, enabled: bool) -> None:
        self.update_user(user_name, enabled=enabled)
