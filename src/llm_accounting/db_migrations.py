import logging
import os
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy.engine.url import make_url
from pathlib import Path
import sys
from typing import Optional # Import Optional

logger = logging.getLogger(__name__)

def run_migrations(db_url: Optional[str] = None):
    """
    Checks and applies any pending database migrations for the given DB URL.
    If no DB URL is provided, it attempts to get it from LLM_ACCOUNTING_DB_URL env var.
    Migrations are skipped silently if no DB URL can be determined.
    """
    migration_logger = logging.getLogger(__name__ + ".migrations") 
    
    # If db_url is not provided, try to get it from environment variable
    if db_url is None:
        db_url = os.getenv("LLM_ACCOUNTING_DB_URL")

    if not db_url:
        # Silently skip migrations if no DB URL is found.
        # This is crucial for client apps that don't need/want migrations.
        return

    # Determine alembic script location dynamically
    # This assumes 'alembic' directory is a sibling of 'llm_accounting' or within it
    # e.g., llm-accounting/src/llm_accounting/db_migrations.py
    # and llm-accounting/alembic/
    current_file_dir = Path(__file__).parent
    # Correct path: from src/llm_accounting/db_migrations.py to project root
    project_root = current_file_dir.parent.parent
    alembic_dir = project_root / "alembic"
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_dir.is_dir():
        # Fallback for different installation paths, e.g., installed package
        try:
            import llm_accounting
            # This path is for installed packages, e.g., site-packages/llm_accounting/
            # so alembic dir would be site-packages/alembic or similar.
            # For now, we assume it's always relative to the project root.
            # If installed, alembic.ini might not be present or needed for client apps.
            # This fallback logic might need refinement for true installed package scenarios.
            alembic_dir = Path(llm_accounting.__file__).parent.parent / "alembic"
            alembic_ini_path = Path(llm_accounting.__file__).parent.parent / "alembic.ini"
        except Exception:
            pass # Will be caught by the next check

    if not alembic_dir.is_dir():
        migration_logger.debug(f"Alembic directory not found at expected path: {alembic_dir}. Skipping migrations.")
        return # Silently skip if alembic scripts are not found


    log_db_url = db_url
    try:
        parsed_url = make_url(db_url)
        if parsed_url.password:
            log_db_url = str(parsed_url._replace(password="****"))
    except Exception:
        pass 
    migration_logger.debug(f"Attempting database migrations for URL: {log_db_url}")
    
    # Configure Alembic's logger to show more details during debugging
    alembic_logger = logging.getLogger("alembic")
    alembic_logger.setLevel(logging.INFO) # Set to INFO or DEBUG for more verbosity

    try:
        # Explicitly load alembic.ini to ensure all configurations, including version_locations, are picked up
        if not alembic_ini_path.is_file():
            migration_logger.warning(f"alembic.ini not found at {alembic_ini_path}. Proceeding with in-memory config, but migrations might fail.")
            alembic_cfg = AlembicConfig()
        else:
            alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))

        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        alembic_command.upgrade(alembic_cfg, "head")
        migration_logger.debug("Database migrations are up to date.")
    except Exception as e:
        # Log the error internally, but don't re-raise to client app
        migration_logger.warning(f"Error running database migrations: {e}", exc_info=True) # Add exc_info for full traceback
