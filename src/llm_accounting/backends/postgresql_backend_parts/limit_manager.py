import logging
import psycopg2
import psycopg2.extras  # For RealDictCursor
from typing import Optional, List
from datetime import datetime

# Corrected import path for models
from llm_accounting.models.limits import UsageLimit, LimitScope, LimitType, TimeInterval, UsageLimitDTO

logger = logging.getLogger(__name__)


class LimitManager:
    def __init__(self, backend_instance, data_inserter_instance):
        self.backend = backend_instance
        self.data_inserter = data_inserter_instance  # This is DataInserter instance

    def get_usage_limits(self,
                         scope: Optional[LimitScope] = None,
                         model: Optional[str] = None,
                         username: Optional[str] = None,
                         caller_name: Optional[str] = None,
                         project_name: Optional[str] = None,
                         filter_project_null: Optional[bool] = None,
                         filter_username_null: Optional[bool] = None,
                         filter_caller_name_null: Optional[bool] = None) -> List[UsageLimitDTO]:
        """
        Retrieves usage limits from the `usage_limits` table based on specified filter criteria.
        Returns a list of UsageLimitData objects.
        """
        self.backend._ensure_connected()
        assert self.backend.conn is not None

        base_query = "SELECT id, scope, limit_type, model_name, username, caller_name, project_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits"
        conditions: List[str] = []
        params: List[Any] = []

        filter_map = {
            "scope": scope.value if scope else None,
            "model_name": model,
            "username": username,
            "caller_name": caller_name,
            "project_name": project_name,
        }

        for column, value in filter_map.items():
            if value is not None:
                conditions.append(f"{column} = %s")
                params.append(value)
        
        # Handle IS NULL / IS NOT NULL filters separately as they don't take parameters
        if username is None: # Only apply IS NULL/NOT NULL if specific username not provided
            if filter_username_null is True:
                conditions.append("username IS NULL")
            elif filter_username_null is False:
                conditions.append("username IS NOT NULL")

        if caller_name is None: # Only apply IS NULL/NOT NULL if specific caller_name not provided
            if filter_caller_name_null is True:
                conditions.append("caller_name IS NULL")
            elif filter_caller_name_null is False:
                conditions.append("caller_name IS NOT NULL")
        
        if project_name is None: # Only apply IS NULL/NOT NULL if specific project_name not provided
            if filter_project_null is True:
                conditions.append("project_name IS NULL")
            elif filter_project_null is False:
                conditions.append("project_name IS NOT NULL")

        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC;"

        limits_data = []
        try:
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                for row_dict in cur:
                    created_at_dt = datetime.fromisoformat(row_dict['created_at']) if row_dict['created_at'] else None
                    updated_at_dt = datetime.fromisoformat(row_dict['updated_at']) if row_dict['updated_at'] else None

                    limits_data.append(UsageLimitDTO(
                        id=row_dict['id'],
                        scope=row_dict['scope'],
                        limit_type=row_dict['limit_type'],
                        max_value=row_dict['max_value'],
                        interval_unit=row_dict['interval_unit'],
                        interval_value=row_dict['interval_value'],
                        model=row_dict['model_name'],
                        username=row_dict['username'],
                        caller_name=row_dict['caller_name'],
                        project_name=row_dict['project_name'],  # Include project_name
                        created_at=created_at_dt,
                        updated_at=updated_at_dt
                    ))
            return limits_data
        except psycopg2.Error as e:
            logger.error(f"Error getting usage limits: {e}")
            raise
        except ValueError as e:
            logger.error(f"Error converting database value for usage limits: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting usage limits: {e}")
            raise

    def insert_usage_limit(self, limit_data: UsageLimitDTO) -> None:
        """
        Converts UsageLimitData to an SQLAlchemy UsageLimit model and passes it to DataInserter.
        """
        logger.info(f"LimitManager converting UsageLimitData to SQLAlchemy model for insertion: {limit_data}")

        sqlalchemy_limit = UsageLimit(
            scope=limit_data.scope,
            limit_type=limit_data.limit_type,
            max_value=limit_data.max_value,
            interval_unit=limit_data.interval_unit,
            interval_value=limit_data.interval_value,
            model=limit_data.model,
            username=limit_data.username,
            caller_name=limit_data.caller_name,
            project_name=limit_data.project_name,  # Pass project_name
            created_at=limit_data.created_at if limit_data.created_at else datetime.now(),
            updated_at=limit_data.updated_at if limit_data.updated_at else datetime.now()
        )

        try:
            self.data_inserter.insert_usage_limit(sqlalchemy_limit)
            logger.info("Successfully requested insert of usage limit via DataInserter.")
        except psycopg2.Error as db_err:
            logger.error(f"Database error during insert_usage_limit in LimitManager: {db_err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during insert_usage_limit in LimitManager: {e}")
            raise

    def set_usage_limit(self, user_id: str, limit_amount: float, limit_type_str: str = "COST", project_name: Optional[str] = None) -> None:  # Added project_name
        """
        Simplified way to set a USER scope, MONTHLY interval limit.
        This method still creates an SQLAlchemy UsageLimit object directly.
        It's a convenience method and doesn't use UsageLimitData for its direct input.
        """
        logger.info(f"Setting usage limit for user '{user_id}', amount {limit_amount}, type '{limit_type_str}', project '{project_name}'.")

        try:
            limit_type_enum = LimitType(limit_type_str)
        except ValueError:
            logger.error(f"Invalid limit_type string: {limit_type_str}. Must be one of {LimitType._member_names_}")  # type: ignore
            raise ValueError(f"Invalid limit_type string: {limit_type_str}")

        usage_limit_model = UsageLimit(
            scope=LimitScope.USER.value,
            limit_type=limit_type_enum.value,
            max_value=limit_amount,
            interval_unit=TimeInterval.MONTH.value,
            interval_value=1,
            username=user_id,
            model=None,
            caller_name=None,
            project_name=project_name,  # Pass project_name
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        try:
            self.data_inserter.insert_usage_limit(usage_limit_model)
            logger.info(f"Successfully set usage limit for user '{user_id}' via DataInserter.")
        except psycopg2.Error as db_err:
            logger.error(f"Database error setting usage limit for user '{user_id}': {db_err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error setting usage limit for user '{user_id}': {e}")
            raise

    def get_usage_limit(self, user_id: str, project_name: Optional[str] = None) -> Optional[List[UsageLimitDTO]]:  # Added project_name
        """
        Retrieves all usage limits (as UsageLimitData) for a specific user.
        """
        logger.info(f"Retrieving all usage limits for user_id: {user_id}, project_name: {project_name}.")
        try:
            return self.get_usage_limits(username=user_id, project_name=project_name)  # Pass project_name
        except Exception as e:
            logger.error(f"Error retrieving usage limits for user '{user_id}': {e}")
            raise
