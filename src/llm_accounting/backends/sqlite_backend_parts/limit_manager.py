import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import text
from llm_accounting.models.limits import LimitScope, UsageLimitDTO

logger = logging.getLogger(__name__)


class SQLiteLimitManager:
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager

    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        conn = self.connection_manager.get_connection()

        now_utc = datetime.now(timezone.utc)
        query = """
            INSERT INTO usage_limits (
                scope, limit_type, max_value, interval_unit, interval_value,
                model, username, caller_name, project_name, created_at, updated_at
            ) VALUES (
                :scope, :limit_type, :max_value, :interval_unit, :interval_value,
                :model, :username, :caller_name, :project_name, :created_at, :updated_at
            )
        """
        params = {
            "scope": limit.scope,
            "limit_type": limit.limit_type,
            "max_value": limit.max_value,
            "interval_unit": limit.interval_unit,
            "interval_value": limit.interval_value,
            "model": limit.model,
            "username": limit.username,
            "caller_name": limit.caller_name,
            "project_name": limit.project_name,
            "created_at": limit.created_at.isoformat() if limit.created_at else now_utc.isoformat(),
            "updated_at": limit.updated_at.isoformat() if limit.updated_at else now_utc.isoformat(),
        }
        conn.execute(text(query), params)
        conn.commit()

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
        filter_username_null: Optional[bool] = None,
        filter_caller_name_null: Optional[bool] = None,
    ) -> List[UsageLimitDTO]:
        conn = self.connection_manager.get_connection()
        query_base = "SELECT id, scope, limit_type, model, username, caller_name, project_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits WHERE 1=1"
        conditions = []
        params_dict: Dict[str, Any] = {}

        if scope:
            conditions.append("scope = :scope")
            params_dict["scope"] = scope.value
        if model:
            conditions.append("model = :model")
            params_dict["model"] = model

        if username is not None:
            conditions.append("username = :username")
            params_dict["username"] = username
        elif filter_username_null is True:
            conditions.append("username IS NULL")
        elif filter_username_null is False:
            conditions.append("username IS NOT NULL")

        if caller_name is not None:
            conditions.append("caller_name = :caller_name")
            params_dict["caller_name"] = caller_name
        elif filter_caller_name_null is True:
            conditions.append("caller_name IS NULL")
        elif filter_caller_name_null is False:
            conditions.append("caller_name IS NOT NULL")

        if project_name is not None:
            conditions.append("project_name = :project_name")
            params_dict["project_name"] = project_name
        elif filter_project_null is True:
            conditions.append("project_name IS NULL")
        elif filter_project_null is False:
            conditions.append("project_name IS NOT NULL")

        if conditions:
            query_base += " AND " + " AND ".join(conditions)

        result = conn.execute(text(query_base), params_dict)
        limits = []
        for row in result.fetchall():
            row_map = row._mapping
            limits.append(
                UsageLimitDTO(
                    id=row_map["id"],
                    scope=row_map["scope"],
                    limit_type=row_map["limit_type"],
                    model=str(row_map["model"]) if row_map["model"] is not None else None,
                    username=str(row_map["username"]) if row_map["username"] is not None else None,
                    caller_name=str(row_map["caller_name"]) if row_map["caller_name"] is not None else None,
                    project_name=str(row_map["project_name"]) if row_map["project_name"] is not None else None,
                    max_value=row_map["max_value"],
                    interval_unit=row_map["interval_unit"],
                    interval_value=row_map["interval_value"],
                    created_at=(datetime.fromisoformat(row_map["created_at"]).replace(tzinfo=timezone.utc) if row_map["created_at"] else None),
                    updated_at=(datetime.fromisoformat(row_map["updated_at"]).replace(tzinfo=timezone.utc) if row_map["updated_at"] else None),
                )
            )
        return limits

    def delete_usage_limit(self, limit_id: int) -> None:
        conn = self.connection_manager.get_connection()
        conn.execute(text("DELETE FROM usage_limits WHERE id = :limit_id"), {"limit_id": limit_id})
        conn.commit()
