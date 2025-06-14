import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import text
from ..base import AuditLogEntry

logger = logging.getLogger(__name__)


class SQLiteAuditLogManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def initialize_audit_log_schema(self) -> None:
        logger.info("Audit log schema is initialized as part of the main database initialization.")

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        conn = self.connection_manager.get_connection()

        query = """
            INSERT INTO audit_log_entries (
                timestamp, app_name, user_name, model, prompt_text,
                response_text, remote_completion_id, project, log_type
            ) VALUES (:timestamp, :app_name, :user_name, :model, :prompt_text, :response_text, :remote_completion_id, :project, :log_type)
        """
        params = {
            "timestamp": entry.timestamp.isoformat(),
            "app_name": entry.app_name,
            "user_name": entry.user_name,
            "model": entry.model,
            "prompt_text": entry.prompt_text,
            "response_text": entry.response_text,
            "remote_completion_id": entry.remote_completion_id,
            "project": entry.project,
            "log_type": entry.log_type,
        }
        try:
            conn.execute(text(query), params)
            conn.commit()
        except Exception as e:  # Rollback handled by ConnectionManager context
            logger.error(f"Failed to log audit event: {e}")
            raise

    def get_audit_log_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        app_name: Optional[str] = None,
        user_name: Optional[str] = None,
        project: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: Optional[int] = None,
        filter_project_null: Optional[bool] = None,
    ) -> List[AuditLogEntry]:
        conn = self.connection_manager.get_connection()

        query_base = "SELECT id, timestamp, app_name, user_name, model, prompt_text, response_text, remote_completion_id, project, log_type FROM audit_log_entries"
        conditions = []
        params_dict: Dict[str, Any] = {}

        if start_date:
            conditions.append("timestamp >= :start_date")
            params_dict["start_date"] = start_date.isoformat()
        if end_date:
            conditions.append("timestamp <= :end_date")
            params_dict["end_date"] = end_date.isoformat()
        if app_name:
            conditions.append("app_name = :app_name")
            params_dict["app_name"] = app_name
        if user_name:
            conditions.append("user_name = :user_name")
            params_dict["user_name"] = user_name

        if project is not None:
            conditions.append("project = :project")
            params_dict["project"] = project
        elif filter_project_null is True:
            conditions.append("project IS NULL")
        elif filter_project_null is False:
            conditions.append("project IS NOT NULL")

        if log_type:
            conditions.append("log_type = :log_type")
            params_dict["log_type"] = log_type

        if conditions:
            query_base += " WHERE " + " AND ".join(conditions)

        query_base += " ORDER BY timestamp DESC"

        if limit is not None:
            query_base += " LIMIT :limit"
            params_dict["limit"] = limit

        results = []
        try:
            result_proxy = conn.execute(text(query_base), params_dict)
            for row in result_proxy.fetchall():
                row_map = row._mapping
                results.append(
                    AuditLogEntry(
                        id=row_map["id"],
                        timestamp=datetime.fromisoformat(row_map["timestamp"]).replace(tzinfo=timezone.utc),
                        app_name=row_map["app_name"],
                        user_name=row_map["user_name"],
                        model=row_map["model"],
                        prompt_text=row_map["prompt_text"],
                        response_text=row_map["response_text"],
                        remote_completion_id=row_map["remote_completion_id"],
                        project=row_map["project"],
                        log_type=row_map["log_type"],
                    )
                )
        except Exception as e:
            logger.error(f"Failed to get audit log entries: {e}")
            raise

        return results
