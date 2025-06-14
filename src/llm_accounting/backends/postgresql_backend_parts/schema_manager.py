import logging

logger = logging.getLogger(__name__)


class SchemaManager:
    def __init__(self, backend_instance):
        self.backend = backend_instance

    # _create_schema_if_not_exists and _create_tables methods are removed.
    # DDL operations are now handled by SQLAlchemy's Base.metadata.create_all
    # (called from PostgreSQLBackend.initialize) and eventually Alembic for migrations.
    # This class is kept for potential future schema-related utility methods
    # that do not perform DDL directly (e.g., schema validation checks via SQLAlchemy inspect).
    # For example, a method like `check_tables_exist(self, table_names: list[str]) -> bool`
    # could be added here if needed elsewhere, using `inspect(self.backend.engine)`.
