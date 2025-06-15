import logging
from typing import List


from sqlalchemy import text


class SQLiteUserManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
        self.logger = logging.getLogger(__name__)

    def create_user(self, user_name: str, ou_name=None, email=None, enabled=True) -> None:
        conn = self.connection_manager.get_connection()
        conn.execute(
            text(
                "INSERT INTO users (user_name, ou_name, email, enabled) "
                "VALUES (:user_name, :ou_name, :email, :enabled)"
            ),
            {"user_name": user_name, "ou_name": ou_name, "email": email, "enabled": 1 if enabled else 0},
        )
        conn.commit()

    def list_users(self) -> List[dict]:
        conn = self.connection_manager.get_connection()
        result = conn.execute(
            text(
                "SELECT id, user_name, ou_name, email, created_at, enabled "
                "FROM users ORDER BY user_name"
            )
        )
        return [dict(row._mapping) for row in result.fetchall()]

    def update_user(self, user_name: str, new_user_name=None, ou_name=None, email=None, enabled=None) -> None:
        fields = []
        params = {"user_name": user_name}
        if new_user_name is not None:
            fields.append("user_name = :new_user_name")
            params["new_user_name"] = new_user_name
        if ou_name is not None:
            fields.append("ou_name = :ou_name")
            params["ou_name"] = ou_name
        if email is not None:
            fields.append("email = :email")
            params["email"] = email
        if enabled is not None:
            fields.append("enabled = :enabled")
            params["enabled"] = 1 if enabled else 0
        if not fields:
            return
        query = "UPDATE users SET " + ", ".join(fields) + " WHERE user_name = :user_name"  # nosec B608
        conn = self.connection_manager.get_connection()
        conn.execute(text(query), params)
        conn.commit()

    def set_user_enabled(self, user_name: str, enabled: bool) -> None:
        self.update_user(user_name, enabled=enabled)
