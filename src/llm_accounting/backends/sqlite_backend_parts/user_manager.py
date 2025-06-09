import logging
from datetime import datetime
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.engine import Connection

class SQLiteUserManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
        self.logger = logging.getLogger(__name__)

    def create_user(self, user_name: str, ou_name: str | None = None, email: str | None = None) -> None:
        conn = self.connection_manager.get_connection()
        conn.execute(
            text(
                "INSERT INTO users (user_name, ou_name, email, created_at, last_enabled_at, enabled)"
                " VALUES (:user_name, :ou_name, :email, :created_at, :last_enabled_at, 1)"
            ),
            {
                "user_name": user_name,
                "ou_name": ou_name,
                "email": email,
                "created_at": datetime.utcnow(),
                "last_enabled_at": datetime.utcnow(),
            },
        )
        conn.commit()

    def list_users(self) -> List[Dict]:
        conn = self.connection_manager.get_connection()
        result = conn.execute(text("SELECT * FROM users ORDER BY user_name"))
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]

    def update_user(self, user_name: str, new_name: str) -> None:
        conn = self.connection_manager.get_connection()
        conn.execute(
            text("UPDATE users SET user_name = :new_name WHERE user_name = :user_name"),
            {"new_name": new_name, "user_name": user_name},
        )
        conn.commit()

    def set_user_active(self, user_name: str, active: bool) -> None:
        conn = self.connection_manager.get_connection()
        fields = {
            "last_enabled_at" if active else "last_disabled_at": datetime.utcnow(),
            "enabled": 1 if active else 0,
        }
        conn.execute(
            text(
                f"UPDATE users SET {', '.join(f'{k} = :{k}' for k in fields.keys())} "
                "WHERE user_name = :user_name"
            ),
            {**fields, "user_name": user_name},
        )
        conn.commit()
