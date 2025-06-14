import logging
from typing import List


class ProjectManager:
    def __init__(self, backend_instance):
        self.backend = backend_instance
        self.logger = logging.getLogger(__name__)

    def create_project(self, name: str) -> None:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute("INSERT INTO projects (name) VALUES (%s)", (name,))
        self.backend.conn.commit()

    def list_projects(self) -> List[str]:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute("SELECT name FROM projects ORDER BY name")
            return [row[0] for row in cur.fetchall()]

    def update_project(self, name: str, new_name: str) -> None:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute("UPDATE projects SET name = %s WHERE name = %s", (new_name, name))
        self.backend.conn.commit()

    def delete_project(self, name: str) -> None:
        self.backend._ensure_connected()
        assert self.backend.conn is not None
        with self.backend.conn.cursor() as cur:
            cur.execute("DELETE FROM projects WHERE name = %s", (name,))
        self.backend.conn.commit()
