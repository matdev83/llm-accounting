from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os # For get_db_url

# Import your Base and models so Alembic knows about them
from llm_accounting.models.base import Base # Changed from src.llm_accounting
# Ensure all models are imported. This line attempts to import the package.
import llm_accounting.models # Changed from src.llm_accounting
# If the above doesn't ensure all model classes are part of Base.metadata,
# you might need explicit imports like:
# from llm_accounting.models.accounting import AccountingEntry
# from llm_accounting.models.audit import AuditLogEntryModel
# from llm_accounting.models.limits import UsageLimit

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata 

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_db_url():
    # Prioritize LLM_ACCOUNTING_DB_URL environment variable
    db_url_env = os.getenv("LLM_ACCOUNTING_DB_URL")
    if db_url_env:
        return db_url_env
    # Fallback to alembic.ini if the env var is not set
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_db_url() # Use the same URL logic
    context.configure(
        url=url, # Pass the URL for offline mode
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite") if url else False # Also here
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    db_url = get_db_url()
    if not db_url:
        raise Exception("Database URL not configured. Set LLM_ACCOUNTING_DB_URL or sqlalchemy.url in alembic.ini.")

    # Create a new configuration for the engine, overriding the URL
    # This ensures Alembic uses the dynamically determined URL.
    # Create a dictionary that can be passed to engine_from_config.
    # engine_from_config expects a dictionary where keys are like 'sqlalchemy.url', 'sqlalchemy.poolclass', etc.
    engine_args = {
        'sqlalchemy.url': db_url,
        'sqlalchemy.poolclass': pool.NullPool # Example, NullPool is good for migrations
    }
    # You can add other engine parameters from alembic.ini if needed,
    # by reading them from config.get_section(config.config_ini_section)
    # and adding them to engine_args with 'sqlalchemy.' prefix.

    # Check if a connection object is available from the config attributes
    # This allows the calling application (e.g., tests) to pass an existing connection
    connection = config.attributes.get('connection', None)

    if connection:
        # If a connection is provided, use it directly
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=db_url.startswith("sqlite") if db_url else False
        )
        # For an externally provided connection, transaction management might be handled by the caller.
        # However, Alembic's default templates often include begin_transaction/run_migrations/commit.
        # If the external connection is already in a transaction, this might be an issue.
        # For now, assume the standard Alembic transactional block is okay or will be adapted by caller.
        with context.begin_transaction():
            context.run_migrations()
    else:
        # No external connection provided, create engine as before
        connectable = engine_from_config(
            engine_args, # Pass the dictionary
            prefix="sqlalchemy.", # Standard prefix
            poolclass=pool.NullPool # Explicitly NullPool for safety
        )
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=db_url.startswith("sqlite") if db_url else False # Batch mode for SQLite
            )
            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
