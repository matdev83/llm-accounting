import logging
from typing import List
from sqlalchemy import text
from sqlalchemy.engine import Connection


class SQLiteProjectManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
        self.logger = logging.getLogger(__name__)

    def create_project(self, name: str) -> None:
        conn = self.connection_manager.get_connection()
        conn.execute(text("INSERT INTO projects (name) VALUES (:name)"), {"name": name})
        conn.commit()

    def list_projects(self) -> List[str]:
        conn = self.connection_manager.get_connection()
        result = conn.execute(text("SELECT name FROM projects ORDER BY name"))
        return [row.name for row in result.fetchall()]

    def update_project(self, name: str, new_name: str) -> None:
        conn = self.connection_manager.get_connection()
        conn.execute(
            text("UPDATE projects SET name = :new_name WHERE name = :name"),
            {"new_name": new_name, "name": name},
        )
        conn.commit()

    def delete_project(self, name: str) -> None:
        conn = self.connection_manager.get_connection()
        conn.execute(text("DELETE FROM projects WHERE name = :name"), {"name": name})
        conn.commit()
