import logging
import psycopg2
import psycopg2.extras # For RealDictCursor
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from ..base import UsageEntry, UsageStats
# Corrected import path for models
from llm_accounting.models.limits import UsageLimit, LimitScope, LimitType, TimeInterval, UsageLimitData

logger = logging.getLogger(__name__)

class LimitManager:
    def __init__(self, backend_instance, data_inserter_instance):
        self.backend = backend_instance
        self.data_inserter = data_inserter_instance # This is DataInserter instance

    def get_usage_limits(self,
                         scope: Optional[LimitScope] = None,
                         model: Optional[str] = None,
                         username: Optional[str] = None,
                         caller_name: Optional[str] = None) -> List[UsageLimitData]: # Return type changed
        """
        Retrieves usage limits from the `usage_limits` table based on specified filter criteria.
        Returns a list of UsageLimitData objects.
        """
        self.backend._ensure_connected()
        assert self.backend.conn is not None

        base_query = "SELECT id, scope, limit_type, model_name, username, caller_name, max_value, interval_unit, interval_value, created_at, updated_at FROM usage_limits" # Explicitly listed columns
        conditions = []
        params = []

        if scope:
            conditions.append("scope = %s")
            params.append(scope.value)
        if model:
            # DB column is model_name, but UsageLimitData expects 'model'
            conditions.append("model_name = %s") 
            params.append(model)
        if username:
            conditions.append("username = %s")
            params.append(username)
        if caller_name:
            conditions.append("caller_name = %s")
            params.append(caller_name)

        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC;"

        limits_data = [] # Changed variable name
        try:
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                for row_dict in cur:
                    # Convert string representations from DB back to Enum values for internal logic if needed,
                    # but UsageLimitData expects raw strings for enum fields.
                    # The original code converted to Enums then to UsageLimit. We'll map directly to UsageLimitData.
                    
                    # Handle potential None for datetime fields before parsing
                    created_at_dt = datetime.fromisoformat(row_dict['created_at']) if row_dict['created_at'] else None
                    updated_at_dt = datetime.fromisoformat(row_dict['updated_at']) if row_dict['updated_at'] else None

                    limits_data.append(UsageLimitData(
                        id=row_dict['id'],
                        scope=row_dict['scope'], # raw string
                        limit_type=row_dict['limit_type'], # raw string
                        max_value=row_dict['max_value'],
                        interval_unit=row_dict['interval_unit'], # raw string
                        interval_value=row_dict['interval_value'],
                        model=row_dict['model_name'], # map model_name from DB to model in dataclass
                        username=row_dict['username'],
                        caller_name=row_dict['caller_name'],
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

    # New method to be called by NeonBackend.insert_usage_limit
    def insert_usage_limit(self, limit_data: UsageLimitData) -> None:
        """
        Converts UsageLimitData to an SQLAlchemy UsageLimit model and passes it to DataInserter.
        """
        logger.info(f"LimitManager converting UsageLimitData to SQLAlchemy model for insertion: {limit_data}")
        
        # Convert UsageLimitData to SQLAlchemy UsageLimit model
        # Note: UsageLimit constructor takes enum values for scope, limit_type, interval_unit
        sqlalchemy_limit = UsageLimit(
            scope=LimitScope(limit_data.scope), # Convert string back to Enum for SQLAlchemy model
            limit_type=LimitType(limit_data.limit_type), # Convert string back to Enum
            max_value=limit_data.max_value,
            interval_unit=TimeInterval(limit_data.interval_unit), # Convert string back to Enum
            interval_value=limit_data.interval_value,
            model=limit_data.model,
            username=limit_data.username,
            caller_name=limit_data.caller_name,
            # id is auto-generated by DB
            # created_at and updated_at can be passed if available in limit_data and not None
            # The UsageLimit model's __init__ handles default datetimes if not provided
            created_at=limit_data.created_at if limit_data.created_at else datetime.now(), # Ensure datetime object
            updated_at=limit_data.updated_at if limit_data.updated_at else datetime.now()  # Ensure datetime object
        )
        
        # If limit_data has an ID, it might imply an update, but UsageLimit's __init__ takes id.
        # For a create operation, ID should typically not be set or be None.
        # The existing UsageLimit.__init__ accepts an id.
        if limit_data.id is not None:
            sqlalchemy_limit.id = limit_data.id

        try:
            # self.data_inserter is an instance of DataInserter class from data_inserter.py
            # Assuming DataInserter.insert_usage_limit expects an SQLAlchemy UsageLimit object
            self.data_inserter.insert_usage_limit(sqlalchemy_limit)
            logger.info(f"Successfully requested insert of usage limit via DataInserter.")
        except psycopg2.Error as db_err:
            logger.error(f"Database error during insert_usage_limit in LimitManager: {db_err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during insert_usage_limit in LimitManager: {e}")
            raise

    def set_usage_limit(self, user_id: str, limit_amount: float, limit_type_str: str = "COST") -> None:
        """
        Simplified way to set a USER scope, MONTHLY interval limit.
        This method still creates an SQLAlchemy UsageLimit object directly.
        It's a convenience method and doesn't use UsageLimitData for its direct input.
        """
        logger.info(f"Setting usage limit for user '{user_id}', amount {limit_amount}, type '{limit_type_str}'.")
        
        try:
            limit_type_enum = LimitType(limit_type_str)
        except ValueError:
            logger.error(f"Invalid limit_type string: {limit_type_str}. Must be one of {LimitType._member_names_}")
            raise ValueError(f"Invalid limit_type string: {limit_type_str}")

        # Create SQLAlchemy UsageLimit object directly
        usage_limit_model = UsageLimit(
            scope=LimitScope.USER, # Enum directly
            limit_type=limit_type_enum, # Enum directly
            max_value=limit_amount,
            interval_unit=TimeInterval.MONTH, # Enum directly
            interval_value=1,
            username=user_id,
            model=None,
            caller_name=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        try:
            self.data_inserter.insert_usage_limit(usage_limit_model) # DataInserter expects SQLAlchemy model
            logger.info(f"Successfully set usage limit for user '{user_id}' via DataInserter.")
        except psycopg2.Error as db_err:
            logger.error(f"Database error setting usage limit for user '{user_id}': {db_err}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error setting usage limit for user '{user_id}': {e}")
            raise

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimitData]]: # Return type changed
        """
        Retrieves all usage limits (as UsageLimitData) for a specific user.
        """
        logger.info(f"Retrieving all usage limits for user_id: {user_id}.")
        try:
            # Calls the updated get_usage_limits which returns List[UsageLimitData]
            return self.get_usage_limits(username=user_id)
        except Exception as e:
            logger.error(f"Error retrieving usage limits for user '{user_id}': {e}")
            raise
