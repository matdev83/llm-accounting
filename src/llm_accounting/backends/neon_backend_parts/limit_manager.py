import logging
import psycopg2
import psycopg2.extras # For RealDictCursor
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from ..base import UsageEntry, UsageStats
from ...models.limits import UsageLimit, LimitScope, LimitType, TimeInterval

logger = logging.getLogger(__name__)

class LimitManager:
    def __init__(self, backend_instance, data_inserter_instance):
        self.backend = backend_instance
        self.data_inserter = data_inserter_instance

    def get_usage_limits(self,
                         scope: Optional[LimitScope] = None,
                         model: Optional[str] = None,
                         username: Optional[str] = None,
                         caller_name: Optional[str] = None) -> List[UsageLimit]:
        """
        Retrieves usage limits from the `usage_limits` table based on specified filter criteria.

        Allows filtering by `scope`, `model_name`, `username`, and `caller_name`.
        Results are ordered by `created_at` in descending order.
        Enum values stored as strings in the DB are converted back to their Enum types.

        Args:
            scope: Optional `LimitScope` enum to filter by.
            model_name: Optional model name string to filter by. (Note: `UsageLimit` dataclass uses `model` field)
            username: Optional username string to filter by.
            caller_name: Optional caller name string to filter by.

        Returns:
            A list of `UsageLimit` objects matching the filters. Returns an empty list if no
            limits match or if no filters are provided and the table is empty.

        Raises:
            ConnectionError: If the database connection is not active.
            ValueError: If a value from the database cannot be converted to its corresponding Enum type.
            psycopg2.Error: If any error occurs during SQL execution (and is re-raised).
            Exception: For any other unexpected errors (and is re-raised).
        """
        self.backend._ensure_connected()
        assert self.backend.conn is not None # Pylance: self.conn is guaranteed to be not None here.

        base_query = "SELECT * FROM usage_limits"
        conditions = []
        params = []

        # Dynamically build the WHERE clause based on provided filters.
        conditions = []
        params = []

        if scope:
            conditions.append("scope = %s")
            params.append(scope.value) # Store enum by its value.
        if model:
            conditions.append("model_name = %s") # DB column is model_name
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
        query += " ORDER BY created_at DESC;" # Most recent limits first.

        limits = []
        try:
            # Uses RealDictCursor for easy mapping to UsageLimit dataclass.
            with self.backend.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                for row_dict in cur:
                    data = dict(row_dict) # Make a mutable copy.
                    # Convert string representations from DB back to Enum objects.
                    # This might raise ValueError if DB data is inconsistent with Enum definitions.
                    data['scope'] = LimitScope(data['scope'])
                    data['limit_type'] = LimitType(data['limit_type'])
                    data['interval_unit'] = TimeInterval(data['interval_unit'])
                    
                    # The UsageLimit dataclass expects a field 'model', but the DB stores it as 'model_name'.
                    # This maps 'model_name' from the DB row to the 'model' field for dataclass instantiation.
                    if 'model_name' in data and 'model' not in data:
                         data['model'] = data.pop('model_name')

                    limits.append(UsageLimit(**data))
            return limits
        except psycopg2.Error as e:
            logger.error(f"Error getting usage limits: {e}")
            raise
        except ValueError as e: # Handles errors from Enum string conversion.
            logger.error(f"Error converting database value to Enum for usage limits: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred getting usage limits: {e}")
            raise

    def set_usage_limit(self, user_id: str, limit_amount: float, limit_type_str: str = "COST") -> None:
        """
        A simplified way to set a usage limit for a user. It creates a `UsageLimit` object
        with `USER` scope and `MONTHLY` interval by default, then calls `insert_usage_limit`.

        This method primarily serves as a convenience. For setting limits with more specific
        scopes, intervals, or other attributes, `insert_usage_limit` should be used directly
        with a fully configured `UsageLimit` object.

        Note: This method attempts an INSERT. If a usage limit that would violate unique
        constraints (e.g. for the same user, scope, type, model, caller) already exists,
        this method will likely raise a `psycopg2.Error` (specifically, an IntegrityError).
        A robust update/insert (upsert) mechanism is not implemented here but would typically
        use `INSERT ... ON CONFLICT DO UPDATE` in PostgreSQL.

        Args:
            user_id: The identifier for the user.
            limit_amount: The maximum value for the limit (e.g., cost amount, token count).
            limit_type_str: String representation of the limit type (e.g., "cost", "requests").
                            Defaults to "cost". Must be a valid `LimitType` enum value.

        Raises:
            ConnectionError: If the database connection is not active.
            ValueError: If `limit_type_str` is not a valid `LimitType`.
            psycopg2.Error: If an error occurs during the underlying `insert_usage_limit` call.
            Exception: For other unexpected errors.
        """
        logger.info(f"Setting usage limit for user '{user_id}', amount {limit_amount}, "
                    f"type '{limit_type_str}'.")
        self.backend._ensure_connected()
        assert self.backend.conn is not None # Pylance: self.conn is guaranteed to be not None here.

        try:
            # Convert the string representation of limit_type to the Enum member.
            limit_type_enum = LimitType(limit_type_str)
        except ValueError: # Raised if limit_type_str is not a valid LimitType value.
            logger.error(f"Invalid limit_type string: {limit_type_str}. "
                        f"Must be one of {LimitType._member_names_}")
            raise ValueError(f"Invalid limit_type string: {limit_type_str}")

        # Create a UsageLimit object with default scope (USER) and interval (MONTHLY).
        usage_limit = UsageLimit(
            scope=LimitScope.USER.value,
            limit_type=limit_type_enum.value,
            max_value=limit_amount,
            interval_unit=TimeInterval.MONTH.value,
            interval_value=1, # Interval value for monthly is 1 (e.g., 1 month).
            username=user_id,
            model=None, # No specific model for this simplified limit.
            caller_name=None, # No specific caller for this simplified limit.
            created_at=datetime.now(), # Set creation timestamp.
            updated_at=datetime.now()  # Set update timestamp.
        )

        try:
            # Call the more general insert_usage_limit method.
            self.data_inserter.insert_usage_limit(usage_limit)
            logger.info(f"Successfully set usage limit for user '{user_id}' "
                        f"via insert_usage_limit call.")
        except psycopg2.Error as db_err:
            logger.error(f"Database error setting usage limit for user '{user_id}': {db_err}")
            raise # Re-raise to allow higher-level handling.
        except Exception as e:
            logger.error(f"Unexpected error setting usage limit for user '{user_id}': {e}")
            raise

    def get_usage_limit(self, user_id: str) -> Optional[List[UsageLimit]]:
        """
        Retrieves all usage limits defined for a specific user.

        This method is a convenience wrapper around `get_usage_limits`, pre-setting
        the `username` filter.

        Args:
            user_id: The identifier of the user whose limits are to be retrieved.

        Returns:
            A list of `UsageLimit` objects associated with the user, or an empty list
            if no limits are found. Can return `None` if an underlying issue occurs,
            though current implementation of get_usage_limits re-raises errors.

        Raises:
            ConnectionError: If the database connection is not active (from underlying call).
            psycopg2.Error: If an error occurs during SQL execution (from underlying call).
            Exception: For other unexpected errors (from underlying call).
        """
        logger.info(f"Retrieving all usage limits for user_id: {user_id}.")
        try:
            # Delegates to the more generic get_usage_limits method.
            return self.get_usage_limits(username=user_id)
        except Exception as e:
            # Log the error and re-raise. Depending on desired API contract,
            # one might choose to return None or an empty list here.
            logger.error(f"Error retrieving usage limits for user '{user_id}': {e}")
            raise
