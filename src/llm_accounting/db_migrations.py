import logging
import os
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy.engine.url import make_url
from pathlib import Path
import sys
from typing import Optional # Import Optional

logger = logging.getLogger(__name__)

def run_migrations(db_url: str):
    """
    Checks and applies any pending database migrations for the given DB URL.
    This function expects a database URL to be provided.
    """
    migration_logger = logging.getLogger(__name__ + ".migrations") 
    
    if not db_url:
        raise ValueError("Database URL must be provided to run migrations.")

    # Determine alembic script location dynamically
    # This assumes 'alembic' directory is a sibling of 'llm_accounting' or within it
    # e.g., llm-accounting/src/llm_accounting/db_migrations.py
    # and llm-accounting/alembic/
    current_file_dir = Path(__file__).parent
    # Correct path: from src/llm_accounting/db_migrations.py to project root
    project_root = current_file_dir.parent.parent
    alembic_dir = project_root / "alembic"
    alembic_ini_path = project_root / "alembic.ini"

    # Fallback for installed packages: try to find alembic dir relative to llm_accounting package
    if not alembic_dir.is_dir():
        try:
            import llm_accounting
            # For installed packages, alembic/ and alembic.ini should be directly within the llm_accounting package directory.
            # Path(llm_accounting.__file__).parent points to .../site-packages/llm_accounting/
            alembic_dir = Path(llm_accounting.__file__).parent / "alembic"
            alembic_ini_path = Path(llm_accounting.__file__).parent / "alembic.ini"
        except Exception as e:
            migration_logger.error(f"Could not determine alembic directory path: {e}")
            raise RuntimeError("Alembic directory could not be found. Cannot run migrations.")

    if not alembic_dir.is_dir():
        raise RuntimeError(f"Alembic directory not found at expected path: {alembic_dir}. Cannot run migrations.")

    # Ensure alembic.ini exists and is loaded from the correct path
    if not alembic_ini_path.is_file():
        raise RuntimeError(f"alembic.ini not found at expected path: {alembic_ini_path}. Cannot run migrations. "
                           "Ensure it's included in the package distribution.")

    log_db_url = db_url
    try:
        parsed_url = make_url(db_url)
        if parsed_url.password:
            log_db_url = str(parsed_url._replace(password="****"))
    except Exception:
        pass 
    migration_logger.info(f"Attempting database migrations for URL: {log_db_url}")
    
    # Configure Alembic's logger to show more details during debugging
    alembic_logger = logging.getLogger("alembic")
    alembic_logger.setLevel(logging.INFO) # Set to INFO or DEBUG for more verbosity

    try:
        # Always load AlembicConfig from the determined alembic.ini path
        alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        alembic_command.upgrade(alembic_cfg, "head")
        migration_logger.info("Database migrations are up to date.")
    except Exception as e:
        migration_logger.error(f"Error running database migrations: {e}", exc_info=True)
        raise # Re-raise the exception to the caller
