import logging
import os
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy.engine.url import make_url

logger = logging.getLogger(__name__)

def run_migrations():
    """Checks and applies any pending database migrations."""
    migration_logger = logging.getLogger(__name__ + ".migrations") 
    
    db_url = os.getenv("LLM_ACCOUNTING_DB_URL")
    alembic_ini_path = "alembic.ini" # Assuming it's in the project root

    if not db_url:
        migration_logger.info(f"LLM_ACCOUNTING_DB_URL not set. Attempting to read from {alembic_ini_path}.")
        try:
            temp_config = AlembicConfig(alembic_ini_path)
            db_url = temp_config.get_main_option("sqlalchemy.url", None)
            if db_url:
                migration_logger.info(f"Found sqlalchemy.url in {alembic_ini_path}: {db_url[:db_url.find('://')+3]}...")
            else:
                migration_logger.warning(f"sqlalchemy.url not found in {alembic_ini_path}.")
        except Exception as e:
            migration_logger.warning(f"Could not read sqlalchemy.url from {alembic_ini_path} for migrations: {e}")

    if not db_url:
        migration_logger.error("Database URL for migrations not found. Skipping migrations. Set LLM_ACCOUNTING_DB_URL or ensure sqlalchemy.url is in alembic.ini.")
        return

    log_db_url = db_url
    try:
        parsed_url = make_url(db_url)
        if parsed_url.password:
            log_db_url = str(parsed_url._replace(password="****"))
    except Exception:
        pass 
    migration_logger.info(f"Running database migrations for URL: {log_db_url}")
    
    try:
        alembic_cfg = AlembicConfig(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        alembic_command.upgrade(alembic_cfg, "head")
        migration_logger.info("Database migrations are up to date.")
    except Exception as e:
        migration_logger.error(f"Error running database migrations: {e}", exc_info=True)
