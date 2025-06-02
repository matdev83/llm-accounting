import logging
import os
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy.engine.url import make_url # Existing
from pathlib import Path # Existing
import sys # Existing
from typing import Optional # Existing

from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext

logger = logging.getLogger(__name__)

def run_migrations(db_url: str) -> Optional[str]: 
    """
    Checks and applies any pending database migrations for the given DB URL.
    This function expects a database URL to be provided.
    Returns the current database revision.
    """
    migration_logger = logging.getLogger(__name__ + ".migrations") 
    
    if not db_url:
        raise ValueError("Database URL must be provided to run migrations.")

    current_file_dir = Path(__file__).parent
    project_root = current_file_dir.parent.parent
    alembic_dir = project_root / "alembic"
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_dir.is_dir():
        try:
            import llm_accounting
            alembic_dir = Path(llm_accounting.__file__).parent / "alembic"
            alembic_ini_path = Path(llm_accounting.__file__).parent / "alembic.ini"
        except Exception as e:
            migration_logger.error(f"Could not determine alembic directory path: {e}")
            raise RuntimeError("Alembic directory could not be found. Cannot run migrations.")

    if not alembic_dir.is_dir():
        raise RuntimeError(f"Alembic directory not found at expected path: {alembic_dir}. Cannot run migrations.")

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
    
    alembic_logger = logging.getLogger("alembic")
    alembic_logger.setLevel(logging.INFO)

    try:
        alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        alembic_command.upgrade(alembic_cfg, "head")
        migration_logger.info("Database migration upgrade to 'head' completed.")

        script = ScriptDirectory.from_config(alembic_cfg)
        with EnvironmentContext(alembic_cfg, script) as context:
            current_rev = context.get_current_revision()
        migration_logger.info(f"Current database revision: {current_rev}")
        return current_rev

    except Exception as e:
        migration_logger.error(f"Error running database migrations: {e}", exc_info=True)
        raise 

def get_head_revision(db_url: str) -> Optional[str]:
    '''
    Retrieves the "head" revision from the Alembic migration scripts.
    '''
    migration_logger = logging.getLogger(__name__ + ".migrations_head_check")
    current_file_dir = Path(__file__).parent
    project_root = current_file_dir.parent.parent
    alembic_dir = project_root / "alembic"
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_dir.is_dir():
        try:
            import llm_accounting 
            alembic_dir = Path(llm_accounting.__file__).parent / "alembic"
            alembic_ini_path = Path(llm_accounting.__file__).parent / "alembic.ini"
        except Exception as e:
            migration_logger.error(f"Could not determine alembic directory path for head revision check: {e}")
            return None

    if not alembic_dir.is_dir():
        migration_logger.error(f"Alembic directory not found at {alembic_dir} for head revision check.")
        return None
    if not alembic_ini_path.is_file():
        migration_logger.error(f"alembic.ini not found at {alembic_ini_path} for head revision check.")
        return None

    try:
        alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url) 

        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        migration_logger.info(f"Current head script revision: {head_rev}")
        return head_rev
    except Exception as e:
        migration_logger.error(f"Error getting head script revision: {e}", exc_info=True)
        return None

def stamp_db_head(db_url: str) -> Optional[str]:
    migration_logger = logging.getLogger(__name__ + ".migrations_stamp")
    current_file_dir = Path(__file__).parent
    project_root = current_file_dir.parent.parent 
    alembic_dir = project_root / "alembic"
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_dir.is_dir():
        try:
            import llm_accounting
            package_root = Path(llm_accounting.__file__).parent
            alembic_dir = package_root / "alembic"
            alembic_ini_path = package_root / "alembic.ini"
            migration_logger.info(f"Using package path for Alembic in stamp_db_head: {alembic_dir}")
        except ImportError:
            migration_logger.error("llm_accounting package not found for Alembic path resolution in stamp_db_head.")
            return None
        except Exception as e:
            migration_logger.error(f"Error determining alembic directory path for package in stamp_db_head: {e}", exc_info=True)
            return None

    if not alembic_dir.is_dir():
        migration_logger.error(f"Alembic directory not found at {alembic_dir}. Cannot stamp database.")
        return None
    if not alembic_ini_path.is_file():
        migration_logger.error(f"alembic.ini not found at {alembic_ini_path}. Cannot stamp database.")
        return None

    log_db_url_str = str(db_url)
    if db_url:
        try:
            parsed_url = make_url(db_url) 
            if parsed_url.password:
                log_db_url_str = str(parsed_url._replace(password="****"))
        except Exception:
            pass 
    migration_logger.info(f"Attempting to stamp database for URL context: {log_db_url_str}")
    
    try:
        alembic_cfg = AlembicConfig(file_=str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        alembic_command.stamp(alembic_cfg, "head")
        migration_logger.info(f"Successfully stamped database {log_db_url_str} with head revision.")

        script = ScriptDirectory.from_config(alembic_cfg)
        db_stamped_rev: Optional[str] = None
        try:
            with EnvironmentContext(alembic_cfg, script) as context: 
                db_stamped_rev = context.get_current_revision()
        except Exception as e_ctx:
            migration_logger.warning(f"Could not read revision from DB after stamp, will use script head: {e_ctx}")

        if db_stamped_rev:
            migration_logger.info(f"Database is now at revision: {db_stamped_rev} (stamped).")
            return db_stamped_rev
        else: # Fallback to script head if DB read failed or returned None
            head_rev_from_script = script.get_current_head()
            if head_rev_from_script:
                migration_logger.info(f"Database stamped with script head: {head_rev_from_script} (DB read for confirmation failed or returned None).")
                return head_rev_from_script
            else:
                migration_logger.warning("Could not determine head revision after stamping (script head and DB read failed).")
                return None
            
    except Exception as e:
        migration_logger.error(f"Error stamping database {log_db_url_str} with head revision: {e}", exc_info=True)
        return None
